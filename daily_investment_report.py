# -*- coding: utf-8 -*-
"""
daily_investment_report.py — 毎朝7:30 投資日次レポート生成
Gemini で市場情報を収集 → Claude で投資OSルール適用 → Notion に書き込む
"""

import sys
from datetime import datetime

from setup_env import load_env
load_env()

from config import NOTION_PAGES
from notion_write_safe import write_to_notion_page, create_daily_page
from ai_client import ask_gemini, ask_claude
from logger import write_log, print_safe

INVESTMENT_ID    = NOTION_PAGES["investment"]
CURRENT_STATE_ID = NOTION_PAGES["current_state"]
INVEST_OS_ID     = NOTION_PAGES["invest_os"]


def get_market_info() -> str:
    """Gemini で本日の市場概況を取得"""
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""本日（{today}）の市場概況を簡潔にまとめてください。

以下を含めてください：
- VIX 現在値
- 日経225 / S&P500 の前日比
- 本日〜今週の主要経済指標（FOMC・CPI・雇用統計等）
- 国策テーマ銘柄の動向

出力は箇条書きで200文字以内。情報の確実性に [確定]/[推測] タグを付けること。"""
    try:
        return ask_gemini(prompt)
    except Exception as e:
        return f"[未確認] Gemini取得失敗: {e}"


def apply_invest_os_rules(market_info: str) -> str:
    """Claude で投資OS v9.x のルールを市場情報に適用"""
    system = """あなたは矢嶋勇輝の投資OS実行担当AIです。
投資OSv9.xのルールを厳守してください：
- VIX25超：新規エントリー禁止フラグを発動
- 保有銘柄は取得単価×0.90で損切り、×1.30で利確検討
- アンチハルシネーション：数値データがない場合は判定不可として明示する"""

    prompt = f"""以下の市場情報に対して投資OS v9.x のルールを適用し、本日のモード判定を出力してください。

【市場情報】
{market_info}

【出力形式】
⚡ 結論（本日モード：通常稼働 / 警戒 / エントリー禁止）
VIX判定：
推奨アクション（3点以内）：
注意イベント："""

    try:
        return ask_claude(prompt, system=system, smart=False)
    except Exception as e:
        return f"[エラー] Claude処理失敗: {e}"


def main() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_str = datetime.now().strftime("%Y-%m-%d")
    write_log("daily_investment_report 起動")
    print_safe(f"[投資日次レポート] {now} 起動")

    try:
        market_info = get_market_info()
        write_log("Gemini市場情報取得完了")

        analysis = apply_invest_os_rules(market_info)
        write_log("Claude分析完了")

        body = f"【市場概況】\n{market_info}\n\n【投資OS判定】\n{analysis}"

        # Current State に簡易サマリを追記
        heading = f"📊 [投資日次レポート生成] {now}"
        write_to_notion_page(CURRENT_STATE_ID, heading, "レポートが生成されました。")

        # 20_Investment に日次ページを作成して詳細を記載
        page_id = create_daily_page(INVESTMENT_ID, date_str, "投資日次レポート")
        if page_id:
            write_to_notion_page(page_id, f"📊 {date_str} 投資日次レポート", body, level=1)
            write_log(f"投資日次ページ作成: {page_id}")

        print_safe("✅ 投資日次レポート完了")

    except Exception as e:
        msg = f"daily_investment_report エラー: {e}"
        write_log(msg)
        print_safe(f"❌ {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
