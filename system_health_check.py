# -*- coding: utf-8 -*-
"""
system_health_check.py — 毎朝7:00 システム健全性チェック
エラーを集計して Current State に書き込む
"""

import sys
from datetime import datetime
from pathlib import Path

from setup_env import load_env
load_env()

from config import NOTION_PAGES, DISPATCHER_LOG, HEALTH_LOG, CLAUDE_MODEL
from notion_write_safe import write_to_notion_page
from logger import write_log, print_safe, get_recent_errors

CURRENT_STATE_ID = NOTION_PAGES["current_state"]

CHECKS = [
    ("ANTHROPIC_API_KEY", "Claude API"),
    ("OPENAI_API_KEY",    "OpenAI API"),
    ("GEMINI_API_KEY",    "Gemini API"),
    ("NOTION_TOKEN",      "Notion API"),
]


def check_env_vars() -> list[str]:
    import os
    issues = []
    for env_key, label in CHECKS:
        if not os.environ.get(env_key, ""):
            issues.append(f"環境変数 {env_key} が未設定")
    return issues


def check_logs() -> list[str]:
    issues = []
    for log_path, label in [(DISPATCHER_LOG, "dispatcher_log"), (HEALTH_LOG, "health_sync_log")]:
        errors = get_recent_errors(log_path, hours=24)
        if errors:
            issues.append(f"{label}: 直近24hに{len(errors)}件のエラー")
    return issues


def check_claude_model() -> list[str]:
    """廃止モデル参照が残っていないかチェック"""
    deprecated = ["claude-3-haiku-20240307", "claude-3-sonnet", "claude-2"]
    issues = []
    for py in Path(".").glob("*.py"):
        text = py.read_text(encoding="utf-8", errors="replace")
        for d in deprecated:
            if d in text:
                issues.append(f"{py.name} に廃止モデル '{d}' の参照あり → {CLAUDE_MODEL} に更新してください")
    return issues


def main() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    write_log("system_health_check 起動")

    all_issues: list[str] = []
    all_issues += check_env_vars()
    all_issues += check_logs()
    all_issues += check_claude_model()

    if all_issues:
        body = f"{len(all_issues)}件の異常を検出しました。\n\n"
        body += "\n".join(f"・{i}" for i in all_issues)
        heading = f"⚠️ [システムヘルスチェック] {now}"
    else:
        body = "異常なし。全システム正常稼働中。"
        heading = f"✅ [システムヘルスチェック] {now}"

    write_to_notion_page(CURRENT_STATE_ID, heading, body)
    write_log(f"ヘルスチェック完了: {len(all_issues)}件の異常")
    print_safe(f"{'⚠️' if all_issues else '✅'} ヘルスチェック完了 — 異常{len(all_issues)}件")


if __name__ == "__main__":
    main()
