# -*- coding: utf-8 -*-
"""
consensus.py — Personal OS Consensus メインスクリプト
Claude・Gemini・OpenAIの3社に同じ質問を投げて統合分析を生成し、Notionに保存する

使い方：
  venv\\Scripts\\activate
  python consensus.py
"""

import asyncio
import os
import re
import sys
from datetime import datetime, timezone

# Windows環境でのUTF-8出力対応
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

# .envファイルから環境変数を読み込む
from dotenv import load_dotenv
load_dotenv()

# ─── 使用モデル設定 ───────────────────────────────────────────────────────────
CLAUDE_MODEL  = "claude-sonnet-4-6"   # メイン作業モデル
GEMINI_MODEL  = "gemini-2.5-flash"    # 情報収集・裏取り
OPENAI_MODEL  = "gpt-4o"              # 汎用

# ─── Gemini 役割指示 ──────────────────────────────────────────────────────────
GEMINI_ROLE_INSTRUCTION = """あなたの役割は「観点出し」です。
以下のルールを必ず守ってください：
- 回答は400字以内に収めてください
- 箇条書きで3〜5点に絞って回答してください
- 長文の説明・設計・統合判断はしないでください
- 調査・比較・ファクト確認に集中してください
"""

# ─── Notionプロパティ名（DBスキーマと一致させる）──────────────────────────────
DB_ID = os.environ.get("NOTION_DATABASE_ID", "")

# ─── タイムアウト設定 ─────────────────────────────────────────────────────────
RUNNING_TIMEOUT_MINUTES = 60

# ─── 統合分析プロンプトテンプレート（8セクション出力形式）──────────────────────
SYNTHESIS_PROMPT_TEMPLATE = """\
以下は同じ質問に対する複数のAIの回答です（{mode}モード）。{unavailable_note}
【質問】
{question}

【Claudeの回答】
{claude_section}

【Geminiの回答】
{gemini_section}

【OpenAIの回答】
{openai_section}

以下の8セクション形式で統合分析を作成してください：

### 結論
1〜2行で要点をまとめてください

### 根拠
判断の根拠（各社の主張で一致した点、根拠データ）

### リスク
潜在的な落とし穴・反対意見

### 推奨アクション
具体的な次の一歩

### タイプ判定
質問の種類: dev_task / doc_task / research / discussion のいずれか

### 推奨成果物
タイプ判定に応じた成果物:
- dev_task: PR
- doc_task: Notion ページ
- research: 調査メモ
- discussion: 議論まとめ

### Human Review Required
true / false

### Next Route
次に何をすべきか（例: Handoff 起票、人間レビュー、追加調査）\
"""


# ════════════════════════════════════════════════════════════════════════
# 0. エラー記録ユーティリティ
# ════════════════════════════════════════════════════════════════════════
from notion_utils import query_database, update_page_properties, to_rich_text, get_page

# APIキーのマスク対象パターン（sk-ant- / sk-proj- / AIza / ntn_）
_SECRET_PATTERNS = [
    (r'sk-ant-[A-Za-z0-9\-_]+',  'sk-ant-***'),
    (r'sk-proj-[A-Za-z0-9\-_]+', 'sk-proj-***'),
    (r'AIza[A-Za-z0-9\-_]+',     'AIza***'),
    (r'ntn_[A-Za-z0-9\-_]+',     'ntn_***'),
]


def mask_secrets(text: str) -> str:
    """APIキー文字列をマスクして安全なテキストにする"""
    for pattern, replacement in _SECRET_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


def classify_error(e: Exception) -> str:
    """例外メッセージからエラー種別を判定する"""
    msg = str(e).lower()
    if "anthropic" in msg or "claude" in msg:
        return "API_ERROR_CLAUDE"
    if "gemini" in msg or "google" in msg:
        return "API_ERROR_GEMINI"
    if "openai" in msg or "gpt" in msg:
        return "API_ERROR_OPENAI"
    if "notion" in msg:
        return "NOTION_WRITE_ERROR"
    return "UNKNOWN_ERROR"


def record_error(page_id: str, error_type: str, detail: str) -> None:
    """
    エラー発生時にStatusをErrorに変更し、Synthesisにエラー情報を記録する。

    error_type:
        API_ERROR_CLAUDE / API_ERROR_GEMINI / API_ERROR_OPENAI
        NOTION_WRITE_ERROR / TIMEOUT_ERROR / UNKNOWN_ERROR
    """
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    safe_detail = mask_secrets(str(detail))[:500]  # APIキーマスク + 500字制限
    error_text = f"[{error_type}]\n発生時刻: {now_str}\n詳細: {safe_detail}\n"

    try:
        update_page_properties(page_id, {
            "Status":    {"select": {"name": "Error"}},
            "Synthesis": {"rich_text": to_rich_text(error_text)},
        })
    except Exception as write_err:
        # Notion書き込み自体が失敗した場合はStatusだけ変更を試みる
        print(f"❌ エラー記録失敗（Notion書き込みエラー）: {write_err}")
        try:
            update_page_properties(page_id, {"Status": {"select": {"name": "Error"}}})
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════
# 1. Notionから Pending 行を取得
# ════════════════════════════════════════════════════════════════════════


def get_running_pages() -> list[dict]:
    """StatusがRunningの行をすべて取得する"""
    return query_database(
        DB_ID,
        filter_body={"property": "Status", "select": {"equals": "Running"}},
    )


def handle_running_timeouts() -> None:
    """
    起動時に実行。RUNNING_TIMEOUT_MINUTES分以上Runningのままの行をErrorに変更する。
    Synthesis冒頭に "ERROR: タイムアウト" と経過時間を記録する。
    """
    running_pages = get_running_pages()
    if not running_pages:
        return

    now = datetime.now(timezone.utc)
    for page in running_pages:
        page_id = page["id"]
        # Notion APIはlast_edited_timeをページトップレベルで返す
        last_edited_str = page.get("last_edited_time", "")
        if not last_edited_str:
            continue

        last_edited = datetime.fromisoformat(last_edited_str.replace("Z", "+00:00"))
        elapsed_minutes = (now - last_edited).total_seconds() / 60

        if elapsed_minutes >= RUNNING_TIMEOUT_MINUTES:
            error_text = (
                f"ERROR: タイムアウト\n"
                f"（{int(elapsed_minutes)}分間Runningのまま → 自動的にErrorに変更）\n"
            )
            update_page_properties(page_id, {
                "Status":    {"select": {"name": "Error"}},
                "Synthesis": {"rich_text": to_rich_text(error_text)},
            })
            print(f"⏰ タイムアウト検出 → Error に変更: {page_id[:8]}... ({int(elapsed_minutes)}分経過)")


def get_pending_questions() -> list[dict]:
    """NotionのAI Consensus LogからStatus=Pendingの行を古い順（FIFO）で取得する"""
    return query_database(
        DB_ID,
        filter_body={"property": "Status", "select": {"equals": "Pending"}},
        sorts=[{"timestamp": "created_time", "direction": "ascending"}],
    )


def set_status(page_id: str, status: str) -> None:
    """指定ページのStatusを変更する"""
    update_page_properties(page_id, {"Status": {"select": {"name": status}}})


def try_claim_page(page_id: str) -> bool:
    """
    楽観的ロック：PendingをRunningに変更し、変更を再確認する。
    別プロセスが先に処理を始めていた場合はFalseを返す。

    手順：
    1. StatusをRunningに更新
    2. 再取得してRunningになっているか確認
    3. Runningでなければ別プロセスが処理中 → False を返す
    """
    set_status(page_id, "Running")
    refreshed = get_page(page_id)
    status_name = (
        refreshed.get("properties", {})
        .get("Status", {})
        .get("select", {})
        .get("name")
    )
    return status_name == "Running"


def get_question_text(page: dict) -> str:
    """ページオブジェクトから質問テキストを取り出す"""
    titles = page["properties"]["Question"]["title"]
    return "".join(t["plain_text"] for t in titles)


# ════════════════════════════════════════════════════════════════════════
# 2. 各AIへの問い合わせ（並列実行）
# ════════════════════════════════════════════════════════════════════════

async def ask_claude(question: str) -> tuple[str, bool]:
    """
    Claudeに質問する（最大3回リトライ）
    Returns: (response_text, is_success)
    """
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    system = (
        "あなたは慎重で構造的な分析を行うAIです。"
        "回答の最後に[確定][推測][未確認]のいずれかのタグを付けてください。"
    )

    for attempt in range(3):
        try:
            resp = await client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": question}],
            )
            return resp.content[0].text, True
        except Exception as e:
            if attempt == 2:
                masked_error = mask_secrets(str(e))
                error_type = classify_error(e)
                return f"Claude unavailable: {error_type}\n{masked_error[:200]}", False
            await asyncio.sleep(2 ** attempt)  # 指数バックオフ


async def ask_gemini(question: str) -> tuple[str, bool]:
    """
    Geminiに質問する（APIキーがない場合はスキップ）
    Returns: (response_text, is_success)
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return "[スキップ：Gemini APIキー未設定]", False

    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)

    for attempt in range(3):
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=GEMINI_ROLE_INSTRUCTION + question,
                    config=types.GenerateContentConfig(max_output_tokens=2048),
                ),
            )
            return resp.text, True
        except Exception as e:
            if attempt == 2:
                masked_error = mask_secrets(str(e))
                error_type = classify_error(e)
                return f"Gemini unavailable: {error_type}\n{masked_error[:200]}", False
            await asyncio.sleep(2 ** attempt)


async def ask_openai(question: str) -> tuple[str, bool]:
    """
    OpenAI GPTに質問する（最大3回リトライ）
    Returns: (response_text, is_success)
    """
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    for attempt in range(3):
        try:
            resp = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": question}],
                max_tokens=2048,
            )
            return (resp.choices[0].message.content or ""), True
        except Exception as e:
            if attempt == 2:
                masked_error = mask_secrets(str(e))
                error_type = classify_error(e)
                return f"OpenAI unavailable: {error_type}\n{masked_error[:200]}", False
            await asyncio.sleep(2 ** attempt)


async def ask_all_ai(question: str) -> dict:
    """
    3社に並列で問い合わせて各社の回答と成否フラグを返す。
    Returns: {
        "claude": {"text": str, "ok": bool},
        "gemini": {"text": str, "ok": bool},
        "openai": {"text": str, "ok": bool},
    }
    """
    claude_result, gemini_result, openai_result = await asyncio.gather(
        ask_claude(question),
        ask_gemini(question),
        ask_openai(question),
    )
    return {
        "claude": {"text": claude_result[0], "ok": claude_result[1]},
        "gemini": {"text": gemini_result[0], "ok": gemini_result[1]},
        "openai": {"text": openai_result[0], "ok": openai_result[1]},
    }


# ════════════════════════════════════════════════════════════════════════
# 3. 統合分析の生成
# ════════════════════════════════════════════════════════════════════════

async def synthesize(question: str, claude_r: str, gemini_r: str, gpt_r: str,
                     *, claude_success: bool = True,
                     gemini_success: bool = True,
                     openai_success: bool = True) -> str:
    """
    各社の回答をもとに統合分析を生成する。
    失敗したAIがある場合、利用可能なAIのみで2社合議モードで統合分析を生成する。
    Claude失敗時はOpenAI APIでSynthesis生成を行う（フォールバック）。
    Returns: 統合分析テキスト
    """
    # 失敗AIの特定
    failed_ais = []
    if not claude_success:
        failed_ais.append("Claude")
    if not gemini_success:
        failed_ais.append("Gemini")
    if not openai_success:
        failed_ais.append("OpenAI")

    # 各社の回答セクションを組み立て（失敗AIは利用不可と表示）
    claude_section = claude_r if claude_success else f"（利用不可: {claude_r[:100]}）"
    gemini_section = gemini_r if gemini_success else f"（利用不可: {gemini_r[:100]}）"
    openai_section = gpt_r if openai_success else f"（利用不可: {gpt_r[:100]}）"

    if failed_ais:
        failed_names = "/".join(failed_ais)
        available_count = 3 - len(failed_ais)
        parties = f"{available_count}社"
        mode = f"{parties}合議（{failed_names} unavailable）"
        unavailable_note = (
            f"\n注意：今回は{failed_names}が利用できませんでした。"
            f"利用可能なAIの{parties}合議として統合分析を生成してください。\n"
            f"\nSynthesis冒頭に以下のセクションを含めてください：\n"
            f"## {failed_names} unavailable\n"
            f"今回は{failed_names}が利用できなかったため、"
            f"残りのAIの{parties}合議として統合分析を行います。\n"
        )
    else:
        parties = "3社"
        mode = "3社合議"
        unavailable_note = ""

    prompt = SYNTHESIS_PROMPT_TEMPLATE.format(
        mode=mode,
        unavailable_note=unavailable_note,
        question=question,
        claude_section=claude_section,
        gemini_section=gemini_section,
        openai_section=openai_section,
    )

    # Synthesis生成：通常はClaude、Claude失敗時はOpenAIにフォールバック
    if claude_success:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        synthesis_text = resp.content[0].text
    else:
        # Claude失敗時：OpenAIでSynthesis生成
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
        )
        synthesis_text = resp.choices[0].message.content or ""

    return synthesis_text


# ════════════════════════════════════════════════════════════════════════
# 4. Notionへの書き戻し
# ════════════════════════════════════════════════════════════════════════

def write_back_to_notion(page_id: str,
                          claude_r: str, gemini_r: str, gpt_r: str,
                          synthesis: str) -> None:
    """3社の回答・統合分析・ステータスをNotionページに書き戻す"""
    now_iso = datetime.now(timezone.utc).isoformat()

    # 書き戻すプロパティを組み立てる
    properties = {
        "Status":          {"select": {"name": "Complete"}},
        "Claude_Response": {"rich_text": to_rich_text(claude_r)},
        "Gemini_Response": {"rich_text": to_rich_text(gemini_r)},
        "GPT_Response":    {"rich_text": to_rich_text(gpt_r)},
        "Synthesis":       {"rich_text": to_rich_text(synthesis)},
        "Completed":       {"date": {"start": now_iso}},
    }

    # Depthが空のときだけ Consensus を入れる（既設定は上書きしない）
    page = get_page(page_id)
    depth_prop = page.get("properties", {}).get("Depth", {})
    depth_current = depth_prop.get("select")

    # None・空dict・{"name": None}いずれも「未設定」として扱う
    depth_is_empty = (
        depth_current is None
        or depth_current == {}
        or depth_current.get("name") is None
    )

    if depth_is_empty:
        properties["Depth"] = {"select": {"name": "Consensus"}}

    update_page_properties(page_id, properties)


# ════════════════════════════════════════════════════════════════════════
# 5. メイン処理
# ════════════════════════════════════════════════════════════════════════

async def process_one(page: dict) -> None:
    """1件の質問を処理する"""
    page_id  = page["id"]
    question = get_question_text(page)

    print(f"\n{'='*60}")
    print(f"質問: {question[:60]}...")
    print(f"{'='*60}")

    # 楽観的ロック：RunningにしてからNotion再取得で確認
    if not try_claim_page(page_id):
        print("⏭ 別プロセスが処理中のためスキップ")
        return
    print("▶ Status → Running")

    # 3社に並列問い合わせ
    print("▶ 3社に並列問い合わせ中...")
    results = await ask_all_ai(question)
    claude_r = results["claude"]["text"]
    claude_ok = results["claude"]["ok"]
    gemini_r = results["gemini"]["text"]
    gemini_ok = results["gemini"]["ok"]
    gpt_r = results["openai"]["text"]
    openai_ok = results["openai"]["ok"]
    print("  Claude  :", claude_r[:60].replace("\n", " "), "...")
    print("  Gemini  :", gemini_r[:60].replace("\n", " "), "...")
    print("  OpenAI  :", gpt_r[:60].replace("\n", " "), "...")

    # 失敗AIのログ出力
    failed_ais = []
    if not claude_ok:
        failed_ais.append("Claude")
    if not gemini_ok:
        failed_ais.append("Gemini")
    if not openai_ok:
        failed_ais.append("OpenAI")

    if failed_ais:
        failed_names = "/".join(failed_ais)
        print(f"⚠️ {failed_names} unavailable")
        print("   2社合議モードで継続します")

    # 2社以上失敗ならMULTI_API_FAILUREエラー
    success_count = sum([claude_ok, gemini_ok, openai_ok])
    if success_count < 2:
        error_detail = (
            f"成功: {success_count}社 / Claude: {'OK' if claude_ok else 'NG'}"
            f" / Gemini: {'OK' if gemini_ok else 'NG'}"
            f" / OpenAI: {'OK' if openai_ok else 'NG'}"
        )
        record_error(page_id, "MULTI_API_FAILURE", error_detail)
        print(f"❌ 2社以上失敗のためErrorに変更: {error_detail}")
        return

    # 統合分析を生成（各社の成否フラグを渡す）
    print("▶ 統合分析を生成中...")
    synthesis = await synthesize(
        question, claude_r, gemini_r, gpt_r,
        claude_success=claude_ok,
        gemini_success=gemini_ok,
        openai_success=openai_ok,
    )

    # Notionに書き戻し（1社失敗時でもStatusはComplete）
    try:
        write_back_to_notion(page_id, claude_r, gemini_r, gpt_r, synthesis)
        if failed_ais:
            mode_label = f"2社合議（{'/'.join(failed_ais)} unavailable）"
        else:
            mode_label = "3社合議"
        print(f"▶ Notionに書き戻し完了 → Status: Complete（{mode_label}）")
    except Exception as e:
        record_error(page_id, "NOTION_WRITE_ERROR", str(e))
        raise


async def main() -> None:
    # 起動時：60分以上Runningのままの行をErrorに変更する
    handle_running_timeouts()

    # Pending行を取得
    pages = get_pending_questions()

    if not pages:
        print("処理待ちの質問はありません。")
        print("NotionのAI Consensus LogにStatus=Pendingの行を追加してから実行してください。")
        return

    print(f"処理待ち: {len(pages)}件")

    # 1件ずつ順番に処理（API負荷分散のため直列処理）
    for page in pages:
        try:
            await process_one(page)
        except Exception as e:
            page_id = page["id"]
            question = get_question_text(page)
            error_type = classify_error(e)
            print(f"❌ エラー（{question[:30]}...）[{error_type}]: {e}")
            record_error(page_id, error_type, str(e))

    print(f"\n✅ 完了しました（{len(pages)}件処理）")
    print("Notionで結果を確認してください: https://www.notion.so/7cb72b048ffa427f808010bd8213d563")


if __name__ == "__main__":
    asyncio.run(main())
