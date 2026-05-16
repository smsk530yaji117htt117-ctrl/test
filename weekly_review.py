# -*- coding: utf-8 -*-
"""
weekly_review.py — 日曜21:00 週次レビュー生成
50_Daily の直近7日分のデータを集約して振り返りページを作成する
"""

import sys
from datetime import datetime, timedelta

from setup_env import load_env
load_env()

from config import NOTION_PAGES
from notion_utils import get_block_children
from notion_write_safe import write_to_notion_page, create_daily_page
from ai_client import ask_claude
from logger import write_log, print_safe

DAILY_ID         = NOTION_PAGES["daily"]
CURRENT_STATE_ID = NOTION_PAGES["current_state"]

SYSTEM = """あなたは矢嶋勇輝の個人OS週次レビュー担当です。
1週間の記録から、以下の4点を簡潔に整理してください：
1. 今週うまくいったこと（具体的な行動ベース）
2. 今週の課題・改善点
3. 来週の優先事項（3点以内）
4. システムへの改善提案（あれば）
[確定]/[推測] タグを使い、推測と事実を明確に区別すること。"""


def get_weekly_summary() -> str:
    """50_Daily の子ページ一覧から直近7日分のタイトルを取得"""
    try:
        blocks = get_block_children(DAILY_ID)
        cutoff = datetime.now() - timedelta(days=7)
        pages: list[str] = []
        for b in blocks:
            if b.get("type") == "child_page":
                title = b.get("child_page", {}).get("title", "")
                # タイトルに日付が含まれるページを対象にする
                for date_offset in range(8):
                    d = (datetime.now() - timedelta(days=date_offset)).strftime("%Y-%m-%d")
                    if d in title:
                        pages.append(title)
                        break
        return "\n".join(pages) if pages else "直近7日分のチェックインページが見つかりませんでした。"
    except Exception as e:
        return f"データ取得失敗: {e}"


def main() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_str = datetime.now().strftime("%Y-%m-%d")
    start_str = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    write_log("weekly_review 起動")
    print_safe(f"[週次レビュー] {now} 起動")

    try:
        summary_data = get_weekly_summary()

        prompt = f"""以下は今週（{start_str}〜{date_str}）の50_Dailyページ一覧です。

{summary_data}

週次レビューとして上記の観点で振り返りをまとめてください。"""

        review = ask_claude(prompt, system=SYSTEM, smart=True)
        write_log("週次レビュー生成完了")

        # 50_Daily に週次レビューページを作成
        page_id = create_daily_page(DAILY_ID, f"{start_str}〜{date_str}", "週次レビュー")
        if page_id:
            write_to_notion_page(page_id, f"📋 週次レビュー {date_str}", review, level=1)

        # Current State にサマリを追記
        heading = f"📋 [週次レビュー生成] {now}"
        body = f"スクリプト：weekly_review.py\n対象期間：{start_str}〜{date_str}\n50_Dailyに週次レビューページを作成しました。"
        write_to_notion_page(CURRENT_STATE_ID, heading, body)

        print_safe("✅ 週次レビュー完了")

    except Exception as e:
        msg = f"weekly_review エラー: {e}"
        write_log(msg)
        print_safe(f"❌ {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
