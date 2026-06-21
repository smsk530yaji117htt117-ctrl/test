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
# Running のまま放置された行を Error に回収するまでの分数。
# main.py の subprocess hard-kill（既定480秒=8分）で consensus が殺されると、
# claim 済みの行は Running のまま残る。旧値60分では回収まで最大約52分（cron5ティック分）
# サイレント停止していた。1回の実処理は hard-kill 上限（=8〜9分）を超えないため、
# それを十分上回りつつ60分より短い 15分 を既定とし、数ティックで回収できるようにする。
# 環境変数 RUNNING_TIMEOUT_MINUTES で上書き可能。
RUNNING_TIMEOUT_MINUTES = int(os.environ.get("RUNNING_TIMEOUT_MINUTES", "15"))

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

以下の8セクション形式で統合分析を作成してください。
見出し（### で始まる行）は追加・削除・改名しないでください。

### 結論
1〜2文で要点をまとめてください

### 根拠
判断の根拠を3点以内で（各社の主張で一致した点、根拠データ）

### リスク
潜在的な落とし穴・反対意見を2点以内で

### 推奨アクション
具体的な次の一歩を1〜3件で

### タイプ判定
primary: dev_task | doc_task | decision | research のいずれか1つ
secondary: 0個以上（該当する型をカンマ区切り。なければ「なし」）
例) primary: dev_task / secondary: doc_task

### 推奨成果物
primary 型に応じた成果物:
- dev_task: 実装 PR
- doc_task: Notion ドキュメント
- decision: 人間が判断するための選択肢提示
- research: 深掘り調査メモ

### Human Review Required
true または false（不可逆・高リスクは true。判断基準は docs/HUMAN_REVIEW_REQUIRED_POLICY.md）

### Next Route
create_handoff | create_doc | no_action | research_more のいずれか1つ
（型→ルート対応は docs/router_rules.md。
 dev_task→create_handoff / doc_task→create_doc / decision→no_action / research→research_more）\
"""


# ════════════════════════════════════════════════════════════════════════
# 0. エラー記録ユーティリティ
# ════════════════════════════════════════════════════════════════════════
from notion_utils import query_database, update_page_properties, to_rich_text, get_page

# マスクは notify.mask_secrets に一本化する（旧 consensus 版は Bearer / Slack・Discord
# webhook URL を取りこぼし、env 実値もマスクしない弱い実装だったため重複を排除）。
# notify → bridge_notion は stdlib のみ・consensus を import しないため循環参照なし。
from notify import mask_secrets


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
        print(f"❌ エラー記録失敗（Notion書き込みエラー）: {mask_secrets(str(write_err))}")
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
                     openai_success: bool = True) -> tuple[str, str]:
    """
    各社の回答をもとに統合分析を生成する。
    失敗したAIがある場合、利用可能なAIのみで2社合議モードで統合分析を生成する。
    Claude失敗時はOpenAI APIでSynthesis生成を行う（フォールバック）。
    Returns: (統合分析テキスト, タグ文字列)
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

    # タグを抽出する
    tag = "未確認"
    if "[確定]" in synthesis_text:
        tag = "確定"
    elif "[推測]" in synthesis_text:
        tag = "推測"

    return synthesis_text, tag


# ════════════════════════════════════════════════════════════════════════
# 4. Notionへの書き戻し
# ════════════════════════════════════════════════════════════════════════

def write_back_to_notion(page_id: str,
                          claude_r: str, gemini_r: str, gpt_r: str,
                          synthesis: str, tag: str) -> None:
    """3社の回答・統合分析・ステータスをNotionページに書き戻す"""
    now_iso = datetime.now(timezone.utc).isoformat()

    # 書き戻すプロパティを組み立てる
    properties = {
        "Status":          {"select": {"name": "Complete"}},
        "Claude_Response": {"rich_text": to_rich_text(claude_r)},
        "Gemini_Response": {"rich_text": to_rich_text(gemini_r)},
        "GPT_Response":    {"rich_text": to_rich_text(gpt_r)},
        "Synthesis":       {"rich_text": to_rich_text(synthesis)},
        "Tags":            {"multi_select": [{"name": tag}]},
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
# 4.5 会議 → Handoff 自動接続（型判定ルーティング）
# ════════════════════════════════════════════════════════════════════════

def route_synthesis_result(synthesis: str, *, source_page_id: str = "") -> None:
    """
    Synthesis テキストを型判定ルーティングに渡し、会議結果を次工程
    （dev_task→Handoff起票 / doc_task→別ループ / decision→人間判断 / research→深掘り）
    へ自動接続する。

    安全方針:
    - 合議ループ本体を壊さないため、ここで起きた例外は握りつぶしてログのみ出す。
    - 実際の Notion 起票は環境変数 ENABLE_MEETING_ROUTING が真のときだけ行う
      （未設定なら dry-run = 起票せずルート判定をログ出力するだけ）。
    - doc_task は合議ループに入れない（meeting_result_processor 側で別ループ扱い）。
    """
    try:
        # 遅延 import：合議ループと依存を切り離す（bridge と同じ思想）
        from meeting_result_processor import route_meeting_result

        dry_run = not _env_truthy(os.environ.get("ENABLE_MEETING_ROUTING"))
        source_url = (
            f"https://www.notion.so/{source_page_id.replace('-', '')}"
            if source_page_id else ""
        )
        result = route_meeting_result(synthesis, source_url=source_url, dry_run=dry_run)
        print(
            f"▶ ルーティング: primary={result.decision.primary_type} "
            f"secondary={result.decision.secondary_types or 'なし'} "
            f"hrr={result.decision.human_review_required} "
            f"actions={[a.route for a in result.actions]} "
            f"{'(dry-run)' if dry_run else '(起票実行)'}"
        )
    except Exception as e:  # noqa: BLE001 — ルーティング失敗で合議を止めない
        print(f"⚠️ ルーティングskip（合議は継続）: {mask_secrets(str(e))[:200]}")


def _env_truthy(value: str | None) -> bool:
    """環境変数の真偽判定（1/true/yes/on を真とみなす）"""
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


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
    synthesis, tag = await synthesize(
        question, claude_r, gemini_r, gpt_r,
        claude_success=claude_ok,
        gemini_success=gemini_ok,
        openai_success=openai_ok,
    )
    print(f"  タグ判定: [{tag}]")

    # Notionに書き戻し（1社失敗時でもStatusはComplete）
    try:
        write_back_to_notion(page_id, claude_r, gemini_r, gpt_r, synthesis, tag)
        if failed_ais:
            mode_label = f"2社合議（{'/'.join(failed_ais)} unavailable）"
        else:
            mode_label = "3社合議"
        print(f"▶ Notionに書き戻し完了 → Status: Complete（{mode_label}）")
    except Exception as e:
        record_error(page_id, "NOTION_WRITE_ERROR", str(e))
        raise

    # 会議 → Handoff 自動接続（型判定ルーティング）
    # 合議ループ本体は壊さない：例外は握りつぶす。実起票は ENABLE_MEETING_ROUTING で
    # 明示的に有効化されるまで dry-run（ログのみ）。doc_task は別ループ扱いで起票しない。
    route_synthesis_result(synthesis, source_page_id=page_id)


async def main() -> None:
    # 設定の fail-fast 検証：DB_ID 未設定なら cron 途中で不透明な Notion 400/404 になる前に止める
    if not DB_ID:
        raise EnvironmentError(
            "NOTION_DATABASE_ID が未設定です。Render の環境変数を確認してください。"
        )

    # 起動時：RUNNING_TIMEOUT_MINUTES（既定15分）以上 Running のままの行を Error に回収する
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
            print(f"❌ エラー（{question[:30]}...）[{error_type}]: {mask_secrets(str(e))}")
            record_error(page_id, error_type, str(e))

    print(f"\n✅ 完了しました（{len(pages)}件処理）")
    result_url = (
        f"https://www.notion.so/{DB_ID.replace('-', '')}" if DB_ID
        else "(NOTION_DATABASE_ID 未設定)"
    )
    print(f"Notionで結果を確認してください: {result_url}")


if __name__ == "__main__":
    asyncio.run(main())
