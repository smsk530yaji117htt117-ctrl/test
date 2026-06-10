# -*- coding: utf-8 -*-
"""
bridge_notion — Render橋（bridge）専用の Notion / HTTP 補助レイヤー

- HTTP は標準ライブラリ urllib のみ（追加ランタイム依存なし）
- Notion 認証は consensus.py / notion_utils.py と同じ環境変数 NOTION_TOKEN を流用
- 書き込み対象は Bridge Queue DB の行と、ダイジェストページへのコメントのみ
"""

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

NOTION_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"

# ─── 確定済みの固定 ID（シークレットではない / 指示書で確定）────────────────────
QUEUE_DB_ID = "ffad28a9f7b648cb8efdff4c47dda4cb"          # Bridge Queue DB
QUEUE_DATA_SOURCE_ID = "8cc53d3d-cf72-4697-84c4-6373498c4d89"
DIGEST_PAGE_ID = "36a5ae2b8d6a81ee8b46e86c7941058f"        # 通知終端のダイジェストページ
ERROR_MENTION_USER_ID = "173d872b-594c-81b4-af4a-000262688c71"  # level=error 時のメンション先

TEXT_LIMIT = 1900  # Notion rich_text 1要素の上限(2000)に対する安全マージン


class HttpError(Exception):
    """HTTP ステータス付きの例外（呼び出し側が status で分岐できる）"""

    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")


def http_post_json(url: str, headers: dict, payload: dict, timeout: int = 30):
    """汎用 JSON POST。(status_code, body) を返す。body は dict か生文字列。"""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, e.read().decode("utf-8", "replace")) from e
    if not raw:
        return status, {}
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw


def _token() -> str:
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise EnvironmentError("NOTION_TOKEN が環境変数に設定されていません")
    return token


def _notion_request(method: str, path: str, body: dict | None = None, timeout: int = 30) -> dict:
    headers = {
        "Authorization": f"Bearer {_token()}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{NOTION_API_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, e.read().decode("utf-8", "replace")) from e


def rich_text(text: str) -> list[dict]:
    """文字列を Notion rich_text 配列へ（2000字制限対策で分割）"""
    text = text or ""
    if not text:
        return [{"type": "text", "text": {"content": ""}}]
    chunks = [text[i:i + TEXT_LIMIT] for i in range(0, len(text), TEXT_LIMIT)]
    return [{"type": "text", "text": {"content": c}} for c in chunks]


def _plain(rich: list | None) -> str:
    return "".join(r.get("plain_text", "") for r in (rich or []))


def row_field(page: dict, name: str) -> str:
    """Queue 行プロパティをテキストで取り出す（title / rich_text / select 対応）"""
    prop = page.get("properties", {}).get(name, {})
    ptype = prop.get("type")
    if ptype == "title":
        return _plain(prop.get("title"))
    if ptype == "rich_text":
        return _plain(prop.get("rich_text"))
    if ptype == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    return ""


# ─── Bridge Queue 操作 ────────────────────────────────────────────────────────

def query_pending() -> list[dict]:
    """Status=Pending を Requested At（created_time）昇順で全件取得"""
    res = _notion_request("POST", f"/databases/{QUEUE_DB_ID}/query", {
        "page_size": 100,
        "filter": {"property": "Status", "select": {"equals": "Pending"}},
        "sorts": [{"timestamp": "created_time", "direction": "ascending"}],
    })
    return res.get("results", [])


def query_recent_done(minutes: int = 30) -> list[dict]:
    """直近 minutes 分の Status=Done 行（dedupe 照会用）"""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    res = _notion_request("POST", f"/databases/{QUEUE_DB_ID}/query", {
        "page_size": 100,
        "filter": {"and": [
            {"property": "Status", "select": {"equals": "Done"}},
            {"timestamp": "created_time", "created_time": {"on_or_after": cutoff}},
        ]},
    })
    return res.get("results", [])


def update_row(page_id: str, status: str | None = None, result: str | None = None) -> dict:
    """Queue 行の Status / Result を更新"""
    props: dict = {}
    if status is not None:
        props["Status"] = {"select": {"name": status}}
    if result is not None:
        props["Result"] = {"rich_text": rich_text(result)}
    return _notion_request("PATCH", f"/pages/{page_id.replace('-', '')}", {"properties": props})


def create_row(name: str, action: str, status: str, result: str,
               target: str = "", payload: str = "") -> dict:
    """Bridge Queue に行を新規作成（SELFTEST結果・notify終端記録などに使用）"""
    props = {
        "Name": {"title": rich_text(name)},
        "Action": {"select": {"name": action}},
        "Target": {"rich_text": rich_text(target)},
        "Payload": {"rich_text": rich_text(payload)},
        "Status": {"select": {"name": status}},
        "Result": {"rich_text": rich_text(result)},
    }
    return _notion_request("POST", "/pages", {
        "parent": {"database_id": QUEUE_DB_ID},
        "properties": props,
    })


def create_comment(page_id: str, rich: list[dict]) -> dict:
    """ページにコメントを作成（Notion Comments API）"""
    return _notion_request("POST", "/comments", {
        "parent": {"page_id": page_id.replace("-", "")},
        "rich_text": rich,
    })
