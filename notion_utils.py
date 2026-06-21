# -*- coding: utf-8 -*-
"""
Notion API クライアント
- テキスト2000文字制限の自動分割
- UTF-8エンコーディング統一
- エラーハンドリング
"""

import os
import sys
import json
import urllib.request
import urllib.error

# Windows環境でのUTF-8出力対応
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

NOTION_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"


def _get_token() -> str:
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise EnvironmentError("NOTION_TOKEN が環境変数に設定されていません")
    return token


def _request(method: str, path: str, body: dict | None = None) -> dict:
    token = _get_token()
    url = f"{NOTION_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        # timeout を付与（hot path。bridge_notion.py の timeout=30 と統一）。
        # 無指定だと Notion API の遅延でソケットが固まり、cron スロットを食い潰す。
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"Notion API エラー {e.code}: {error_body}") from e


def to_rich_text(text: str, chunk_size: int = 1500) -> list:
    """
    Notion rich_text形式へ変換する。
    Notionのtext.contentは1要素2000文字制限があるため、
    安全マージンを取って1500文字ごとに分割する。
    """
    if not text:
        return [{"type": "text", "text": {"content": ""}}]

    chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    return [
        {"type": "text", "text": {"content": chunk}}
        for chunk in chunks
    ]


# ─────────────────────────────────────────────
# 公開 API
# ─────────────────────────────────────────────

def get_page(page_id: str) -> dict:
    """ページ情報を取得"""
    return _request("GET", f"/pages/{page_id.replace('-', '')}")


def query_database(database_id: str, filter_body: dict | None = None, sorts: list | None = None) -> list[dict]:
    """
    データベースをクエリして全行を返す。

    Notion の query は1レスポンス最大100件。`has_more` が真の間 `next_cursor` で
    継続取得する（旧実装は先頭100件で打ち切り、バックログ滞留時に超過分を
    サイレントに取りこぼしていた）。dashboard/notion_reader.query_all と同方式。
    """
    results: list[dict] = []
    start_cursor: str | None = None
    while True:
        body: dict = {"page_size": 100}
        if filter_body:
            body["filter"] = filter_body
        if sorts:
            body["sorts"] = sorts
        if start_cursor:
            body["start_cursor"] = start_cursor
        result = _request("POST", f"/databases/{database_id.replace('-', '')}/query", body)
        results.extend(result.get("results", []))
        if not result.get("has_more"):
            break
        start_cursor = result.get("next_cursor")
        if not start_cursor:
            break
    return results


def update_page_properties(page_id: str, properties: dict) -> dict:
    """ページの複数プロパティを一括更新する"""
    return _request(
        "PATCH",
        f"/pages/{page_id.replace('-', '')}",
        {"properties": properties},
    )
