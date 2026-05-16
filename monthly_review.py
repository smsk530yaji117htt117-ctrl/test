# -*- coding: utf-8 -*-
"""
monthly_review.py — 月末22:30 月次レビュー生成
体重・ストレス・投資・タスク完了数を集計して月次ページを作成する
"""

import sys
from datetime import datetime

from setup_env import load_env
load_env()

from config import NOTION_PAGES
from notion_write_safe import write_to_notion_page, create_daily_page
from ai_client import ask_claude
from logger import write_log, print_safe

DAILY_ID         = NOTION_PAGES["daily"]
CURRENT_STATE_ID = NOTION_PAGES["current_state"]

SYSTEM = """あなたは矢嶋勇輝の個人OS月次レビュー担当です。
以下の観点で月次レビューを作成してください：
1. 健康：体重推移・歩数傾向・ストレスレベルの月平均
2. 投資：月間損益（データがある場合）・ルール遵守度
3. 本業：タスク完了数・自動化の進捗
4. システム改善：今月追加・修正した機能
5. 来月の優先事項（3点以内）
データがない項目は [未確認] として記載すること。"""


def main() -> None:
    now      = datetime.now().strftime("%Y-%m-%d %H:%M")
    year_month = datetime.now().strftime("%Y-%m")
    write_log("monthly_review 起動")
    print_safe(f"[月次レビュー] {now} 起動")

    try:
        prompt = f"""対象月：{year_month}

月次レビューを作成してください。
利用可能なデータが限られている場合は [未確認] を使い、
確認できる範囲でのサマリと来月への提言を出力してください。"""

        review = ask_claude(prompt, system=SYSTEM, smart=True)
        write_log("月次レビュー生成完了")

        # 50_Daily に月次レビューページを作成
        page_id = create_daily_page(DAILY_ID, year_month, "月次レビュー")
        if page_id:
            write_to_notion_page(page_id, f"📊 {year_month} 月次レビュー", review, level=1)

        # Current State にサマリを追記
        heading = f"📊 [月次レビュー生成] {now}"
        body = f"対象月：{year_month}\n50_Dailyに月次レビューページを作成しました。"
        write_to_notion_page(CURRENT_STATE_ID, heading, body)

        print_safe("✅ 月次レビュー完了")

    except Exception as e:
        msg = f"monthly_review エラー: {e}"
        write_log(msg)
        print_safe(f"❌ {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
