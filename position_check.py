# -*- coding: utf-8 -*-
"""
position_check.py — 毎日15:30 投資ポジション管理
保有銘柄データを読み込み、売却シグナルを判定して Current State に書き込む
"""

import sys
from datetime import datetime

from setup_env import load_env
load_env()

from config import NOTION_PAGES
from notion_write_safe import write_to_notion_page
from ai_client import ask_claude
from logger import write_log, print_safe

CURRENT_STATE_ID = NOTION_PAGES["current_state"]
INVEST_OS_ID     = NOTION_PAGES["invest_os"]

SYSTEM = """あなたは矢嶋勇輝の投資OS実行担当AIです。
アンチハルシネーションプロトコル：
- 提供されていない数値を生成・推測しない
- データ不足の場合は「判定不可」として明示する
- ルール：終値<5日MA→売り検討、終値≤取得単価×0.90→損切り、終値≥取得単価×1.30→利確検討"""


def load_position_data() -> str:
    """
    positions.txt が存在すればその内容を返す。
    なければ「データ未提供」を返す。
    ファイル形式例（TSV）:
      銘柄名\t証券コード\t取得単価\t本日終値\t5日移動平均
    """
    from pathlib import Path
    p = Path("positions.txt")
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace")
    return ""


def judge_signals(position_data: str) -> str:
    if not position_data.strip():
        return (
            "⚠️ 売却シグナル判定実行不可｜保有銘柄データ未提供\n\n"
            "positions.txt に以下の形式でデータを入力してください：\n"
            "銘柄名(コード) | 取得単価 | 本日終値 | 5日移動平均\n\n"
            "例）川崎重工(7012) | 3200 | 3050 | 3100"
        )

    prompt = f"""以下の保有銘柄データに対してシグナル判定を実行してください。

{position_data}

投資OS v9.x ルールを適用し、各銘柄の判定結果を表形式で出力してください。
最後に「本日の総合判断」を1行で出力してください。"""

    return ask_claude(prompt, system=SYSTEM)


def main() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    write_log("position_check 起動")

    try:
        position_data = load_position_data()
        result = judge_signals(position_data)

        heading = f"🚨 [ポジションチェック] {now}"
        write_to_notion_page(CURRENT_STATE_ID, heading, result)
        write_log("ポジションチェック完了")
        print_safe("✅ ポジションチェック完了")

    except Exception as e:
        msg = f"position_check エラー: {e}"
        write_log(msg)
        print_safe(f"❌ {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
