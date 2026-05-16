# -*- coding: utf-8 -*-
"""
dispatcher.py — Task Board を読み取り AI にルーティングして結果を Notion に書き戻す
朝8:00 / 夜22:00 に Windows タスクスケジューラから呼び出す
"""

import sys
from datetime import datetime

from setup_env import load_env
load_env()

from config import NOTION_PAGES
from notion_utils import get_block_children
from notion_write_safe import write_to_notion_page
from ai_client import ask_ai
from logger import write_log, print_safe

TASK_BOARD_ID   = NOTION_PAGES["task_board"]
CURRENT_STATE_ID = NOTION_PAGES["current_state"]

SYSTEM_PROMPT = """あなたは矢嶋勇輝の個人OS窓口AIです。
Task Boardのタスクを分析し、以下のルールで処理してください：
- [確定]/[推測]/[未確認] タグを必ず付ける
- 不確実な情報を確定として出力しない
- 構造化・判断・文書作成が主な役割
- ストレスレベル3以上の場合は10_Work以外のタスクを投入しない"""


def get_new_tasks(board_id: str) -> str:
    """Task Board から「📥 新規」セクションのテキストを取得"""
    blocks = get_block_children(board_id)
    capturing = False
    lines: list[str] = []
    for block in blocks:
        btype = block.get("type", "")
        text = ""
        rich = block.get(btype, {}).get("rich_text", [])
        for r in rich:
            text += r.get("plain_text", "")

        if "📥 新規" in text:
            capturing = True
            continue
        if capturing and text.startswith("🔄") or (capturing and text.startswith("👤")):
            break
        if capturing and text:
            lines.append(text)

    return "\n".join(lines) if lines else ""


def process_tasks(tasks_text: str) -> str:
    """Claude にタスクを渡して処理結果を取得"""
    if not tasks_text.strip():
        return "📥 新規タスクはありません。"

    prompt = f"""以下のTask Boardの「新規」タスクを分析してください。

{tasks_text}

各タスクについて：
1. 担当AI（Claude/Gemini/Human）を確認
2. Claude担当のタスクは一次回答を出力
3. Gemini担当のタスクは「Geminiへの依頼」フォーマットで依頼文を出力
4. Human担当のタスクは次アクションを整理して提示

出力は日本語で、[確定]/[推測]/[未確認] タグを付けること。"""

    return ask_ai(prompt, provider="claude_smart", system=SYSTEM_PROMPT)


def main() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    write_log("dispatcher 起動")
    print_safe(f"[dispatcher] {now} 起動")

    try:
        tasks = get_new_tasks(TASK_BOARD_ID)
        write_log(f"タスク取得: {len(tasks)} 文字")

        result = process_tasks(tasks)
        write_log("AI処理完了")

        heading = f"🤖 [AI処理結果] {now}"
        ok = write_to_notion_page(CURRENT_STATE_ID, heading, result)

        if ok:
            write_log("Notion書き込み成功")
            print_safe("✅ 処理完了。Current State に書き込みました。")
        else:
            write_log("Notion書き込み失敗")
            print_safe("❌ Notion書き込みに失敗しました。ログを確認してください。")

    except Exception as e:
        msg = f"dispatcher エラー: {e}"
        write_log(msg)
        print_safe(f"❌ {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
