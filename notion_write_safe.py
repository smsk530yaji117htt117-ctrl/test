# -*- coding: utf-8 -*-
"""
Notion への安全な書き込みユーティリティ
既存スクリプト（dispatcher.py 等）から import して使う

使用例:
    from notion_write_safe import write_to_notion_page
    write_to_notion_page(PAGE_ID, "見出し", "本文テキスト...")
"""

import os
import sys

# 既存スクリプトとの互換のため setup_env も試みる
try:
    from setup_env import load_env
    load_env()
except ImportError:
    pass

from notion_client import append_section, append_paragraph, create_child_page


def write_to_notion_page(page_id: str, heading: str, body: str, level: int = 2) -> bool:
    """
    Notion ページに見出し＋本文を書き込む
    - 2000文字制限を自動処理
    - エラー時は False を返す（例外を外に伝播させない）
    """
    try:
        append_section(page_id, heading, body, level)
        return True
    except Exception as e:
        _err(f"Notion書き込み失敗: {e}")
        return False


def write_log_to_notion(page_id: str, log_text: str) -> bool:
    """
    ログテキストをパラグラフとして Notion ページに追記する
    改行で分割し、各行を個別ブロックとして追記する（長行対応）
    """
    try:
        append_paragraph(page_id, log_text)
        return True
    except Exception as e:
        _err(f"Notion ログ書き込み失敗: {e}")
        return False


def create_daily_page(parent_id: str, date_str: str, title_prefix: str = "") -> str | None:
    """
    日次ページを作成して page_id を返す
    例: create_daily_page(PARENT_ID, "2026-05-16", "投資日次レポート")
    """
    title = f"{title_prefix} {date_str}".strip()
    try:
        result = create_child_page(parent_id, title)
        return result.get("id", "")
    except Exception as e:
        _err(f"Notion ページ作成失敗: {e}")
        return None


def _err(msg: str) -> None:
    text = str(msg)
    try:
        print(text, file=sys.stderr)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode(), file=sys.stderr)
