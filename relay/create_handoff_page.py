# -*- coding: utf-8 -*-
"""
relay/create_handoff_page.py — Handoff spec → Notion AI Handoff DB へ起票

build_handoff_spec() が作った spec を Notion のページ作成 payload に変換し、
AI Handoff DB（環境変数 NOTION_HANDOFF_DB_ID）に1行追加する。

設計:
- HTTP は標準ライブラリ urllib のみ（notion_utils.py / bridge_notion.py と同方式）。
- dry_run=True なら Notion へ書き込まず、組み立てた payload を返す（self-verify 用）。
- スキーマ衝突を避けるため、書き込むプロパティは最小限に絞る:
    Task(title) / Status(select) / Task Type(select) / Execution Mode(select) /
    Notes(rich_text)
  それ以外（handoff_reason / source_url / ルーティング情報）は Notes に集約する。
  ※ Notion スキーマは変更しない（行追加のみ）。プロパティ型が実 DB と異なる場合は
    起票時に Notion がエラーを返すため、初回ライブ起票でマッピングを確認すること。

注意: 実起票は consensus.py 側で ENABLE_MEETING_ROUTING が真のときのみ呼ばれる
（既定は dry-run）。人間レビュー（human_review_required=true）の行は Status=Draft で
起票され、executor へは投入されない。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

NOTION_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"
_TEXT_LIMIT = 2000


def _rich_text(text: str) -> list[dict]:
    """rich_text へ変換（2000字制限を 1500 字ごとに分割）。"""
    text = text or ""
    if not text:
        return [{"type": "text", "text": {"content": ""}}]
    return [
        {"type": "text", "text": {"content": text[i:i + 1500]}}
        for i in range(0, len(text), 1500)
    ]


def build_notion_payload(spec: dict, database_id: str) -> dict:
    """Handoff spec を Notion `POST /pages` の body に変換する。"""
    notes_parts = [spec.get("notes", "")]
    extra = [
        f"Handoff Reason: {spec.get('handoff_reason', '')}",
        f"起票元: {spec.get('source_url') or '（不明）'}",
        f"human_review_required: {str(spec.get('human_review_required')).lower()}",
        f"role: {spec.get('role', 'single')}",
    ]
    notes = (notes_parts[0] + "\n\n---\n" + "\n".join(extra))[:_TEXT_LIMIT * 2]

    properties: dict = {
        "Task": {"title": [{"text": {"content": spec.get("task_title", "")[:_TEXT_LIMIT]}}]},
        "Status": {"select": {"name": spec.get("status", "Draft")}},
        "Notes": {"rich_text": _rich_text(notes)},
    }
    # select 系は値があるときだけ設定（"—" などのプレースホルダは載せない）
    type_label = spec.get("task_type_label")
    if type_label and type_label != "—":
        properties["Task Type"] = {"select": {"name": type_label}}
    exec_mode = spec.get("execution_mode")
    if exec_mode and exec_mode != "—":
        properties["Execution Mode"] = {"select": {"name": exec_mode}}

    return {
        "parent": {"database_id": database_id.replace("-", "")},
        "properties": properties,
    }


def _notion_post(path: str, body: dict) -> dict:
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise EnvironmentError("NOTION_TOKEN が環境変数に設定されていません")
    url = f"{NOTION_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        # timeout を付与（bridge_notion.py / notion_utils.py の timeout=30 と統一）。
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"Notion API エラー {e.code}: {error_body}") from e


def create_handoff_page(
    spec: dict,
    *,
    dry_run: bool = False,
    database_id: str | None = None,
) -> dict:
    """
    Handoff spec を AI Handoff DB に起票する。

    dry_run=True: Notion へ書き込まず {"dry_run": True, "payload": <body>} を返す。
    dry_run=False: 起票して Notion API 応答を返す（NOTION_HANDOFF_DB_ID が必要）。
    """
    db_id = database_id or os.environ.get("NOTION_HANDOFF_DB_ID", "")
    payload = build_notion_payload(spec, db_id or "DRY_RUN_NO_DB")

    if dry_run:
        return {"dry_run": True, "payload": payload}

    if not db_id:
        raise EnvironmentError(
            "NOTION_HANDOFF_DB_ID が未設定のため起票できません（dry_run=True で確認可）"
        )
    return _notion_post("/pages", payload)
