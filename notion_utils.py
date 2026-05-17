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
from typing import Any

# Windows環境でのUTF-8出力対応
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

NOTION_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"
TEXT_LIMIT = 2000  # Notion API の rich_text 1ブロックあたりの文字数上限


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
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"Notion API エラー {e.code}: {error_body}") from e


def to_rich_text(text: str) -> list:
    """
    Notionのrich_text形式に変換する関数。
    NotionはJavaScript（UTF-16）で文字数をカウントするため、
    BMP外の文字（絵文字など）はPythonのlen()より多くカウントされる。
    UTF-16コード単位で正確に2000字以内になるよう分割する。

    引数：
        text: 変換したい文字列
    戻り値：
        Notionに渡せるrich_textブロックのリスト
    """
    if not text:
        return [{"type": "text", "text": {"content": ""}}]

    LIMIT = 2000  # NotionのUTF-16コード単位での上限
    chunks = []
    start = 0

    while start < len(text):
        end = start
        utf16_count = 0
        while end < len(text):
            # BMP外（U+10000以上）の文字はUTF-16で2コード単位になる
            char_len = 2 if ord(text[end]) > 0xFFFF else 1
            if utf16_count + char_len > LIMIT:
                break
            utf16_count += char_len
            end += 1
        chunks.append(text[start:end])
        start = end

    return [{"type": "text", "text": {"content": chunk}} for chunk in chunks]


def _split_text(text: str) -> list[dict]:
    """後方互換用。新規コードはto_rich_text()を使うこと"""
    return to_rich_text(text)


def _paragraph_block(text: str) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _split_text(text)}}


def _heading_block(text: str, level: int = 2) -> dict:
    htype = f"heading_{level}"
    return {"object": "block", "type": htype, htype: {"rich_text": _split_text(text[:TEXT_LIMIT])}}


def _divider_block() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


# ─────────────────────────────────────────────
# 公開 API
# ─────────────────────────────────────────────

def get_page(page_id: str) -> dict:
    """ページ情報を取得"""
    return _request("GET", f"/pages/{page_id.replace('-', '')}")


def get_block_children(block_id: str) -> list[dict]:
    """ブロックの子要素一覧を取得"""
    result = _request("GET", f"/blocks/{block_id.replace('-', '')}/children?page_size=100")
    return result.get("results", [])


def append_paragraph(page_id: str, text: str) -> dict:
    """ページにパラグラフブロックを追記する（2000文字制限を自動処理）"""
    blocks = []
    # テキストが2000文字を超える場合は複数ブロックに分割
    for i in range(0, max(len(text), 1), TEXT_LIMIT):
        chunk = text[i : i + TEXT_LIMIT]
        blocks.append(_paragraph_block(chunk))
    return _request(
        "PATCH",
        f"/blocks/{page_id.replace('-', '')}/children",
        {"children": blocks},
    )


def append_section(page_id: str, heading: str, body: str, level: int = 2) -> dict:
    """見出し＋本文ブロックをまとめてページに追記する"""
    children: list[dict] = [_heading_block(heading, level)]
    for i in range(0, max(len(body), 1), TEXT_LIMIT):
        children.append(_paragraph_block(body[i : i + TEXT_LIMIT]))
    children.append(_divider_block())
    return _request(
        "PATCH",
        f"/blocks/{page_id.replace('-', '')}/children",
        {"children": children},
    )


def update_page_title(page_id: str, title: str) -> dict:
    """ページタイトルを更新する"""
    return _request(
        "PATCH",
        f"/pages/{page_id.replace('-', '')}",
        {"properties": {"title": {"title": [{"text": {"content": title[:TEXT_LIMIT]}}]}}},
    )


def create_child_page(parent_id: str, title: str, content_blocks: list[dict] | None = None) -> dict:
    """親ページの下に新しいページを作成する"""
    body: dict[str, Any] = {
        "parent": {"page_id": parent_id.replace("-", "")},
        "properties": {"title": {"title": [{"text": {"content": title[:TEXT_LIMIT]}}]}},
    }
    if content_blocks:
        body["children"] = content_blocks
    return _request("POST", "/pages", body)


def search_pages(query: str, page_size: int = 10) -> list[dict]:
    """ワークスペース内をキーワード検索する"""
    result = _request("POST", "/search", {"query": query, "page_size": page_size})
    return result.get("results", [])


def query_database(database_id: str, filter_body: dict | None = None) -> list[dict]:
    """データベースをクエリする"""
    body: dict = {"page_size": 100}
    if filter_body:
        body["filter"] = filter_body
    result = _request("POST", f"/databases/{database_id.replace('-', '')}/query", body)
    return result.get("results", [])


def update_page_properties(page_id: str, properties: dict) -> dict:
    """ページの複数プロパティを一括更新する"""
    return _request(
        "PATCH",
        f"/pages/{page_id.replace('-', '')}",
        {"properties": properties},
    )


# ─────────────────────────────────────────────
# 動作確認用
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("Notion API 接続テスト...")
    try:
        results = search_pages("個人OSハブ", page_size=3)
        print(f"✅ 接続成功。検索結果: {len(results)} 件")
        for r in results:
            title = ""
            props = r.get("properties", {})
            for v in props.values():
                if v.get("type") == "title":
                    items = v.get("title", [])
                    if items:
                        title = items[0].get("plain_text", "")
                        break
            print(f"  - {title or '(タイトルなし)'} [{r.get('id', '')}]")
    except Exception as e:
        print(f"❌ エラー: {e}")
