#!/usr/bin/env python
"""Create a Notion AI Handoff page from a labeled Markdown file."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> bool:
        return False


NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"
TEXT_LIMIT = 1900
APPEND_BATCH_SIZE = 80

PROPERTY_FIELDS = [
    "Task",
    "Status",
    "Repository",
    "Goal",
    "Current State",
    "Next Action",
    "Do Not Touch",
    "From AI",
    "To AI",
    "Touched Files",
    "Risks",
    "Commands Run",
    "Notes",
]

V2_SCOPE_FIELDS = [
    "Working Directory",
    "Target Files",
    "Execution Environment",
    "Git Managed",
    "Acceptance Criteria",
    "Escalation Rule",
]

INPUT_FIELDS = PROPERTY_FIELDS + [
    "Raw Log",
] + V2_SCOPE_FIELDS

DEFAULT_PROPERTY_TYPES = {
    "Task": "title",
    "Status": "select",
    "Repository": "rich_text",
    "Goal": "rich_text",
    "Current State": "rich_text",
    "Next Action": "rich_text",
    "Do Not Touch": "rich_text",
    "From AI": "select",
    "To AI": "select",
    "Touched Files": "rich_text",
    "Risks": "rich_text",
    "Commands Run": "rich_text",
    "Notes": "rich_text",
}


class HandoffInputError(ValueError):
    """Raised when the input Markdown is missing required handoff fields."""


def _notion_id(value: str) -> str:
    return value.strip().replace("-", "")


def _split_text(text: str, limit: int = TEXT_LIMIT) -> list[str]:
    if not text:
        return [""]
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def _rich_text(text: str) -> list[dict[str, Any]]:
    return [{"text": {"content": chunk}} for chunk in _split_text(text)]


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise EnvironmentError("NOTION_TOKEN is not set.")

    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{NOTION_API_BASE}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Notion API error {exc.code}: {error_body}") from exc


def parse_labeled_markdown(text: str) -> dict[str, str]:
    text = text.lstrip("\ufeff")
    pattern = re.compile(rf"^({'|'.join(re.escape(field) for field in INPUT_FIELDS)}):\s*(.*)$")
    fields: dict[str, list[str]] = {}
    current: str | None = None

    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            current = match.group(1)
            fields.setdefault(current, [])
            inline_value = match.group(2).strip()
            if inline_value:
                fields[current].append(inline_value)
            continue
        if current:
            fields[current].append(line)

    return {key: "\n".join(value).strip() for key, value in fields.items()}


def validate_fields(fields: dict[str, str], title: str | None) -> None:
    missing = []
    for field in ["Task", "Repository", "Goal", "Current State", "Next Action", "Do Not Touch"]:
        if field == "Task" and title:
            continue
        if not fields.get(field):
            missing.append(field)
    if missing:
        raise HandoffInputError("Missing required fields: " + ", ".join(missing))


def get_parent() -> tuple[dict[str, str], dict[str, Any]]:
    data_source_id = os.environ.get("NOTION_HANDOFF_DATA_SOURCE_ID", "").strip()
    database_id = os.environ.get("NOTION_HANDOFF_DATABASE_ID", "").strip()

    if data_source_id:
        parent = {"type": "data_source_id", "data_source_id": _notion_id(data_source_id)}
        schema = _request("GET", f"/data_sources/{_notion_id(data_source_id)}")
        return parent, schema.get("properties", {})

    if database_id:
        parent = {"type": "database_id", "database_id": _notion_id(database_id)}
        schema = _request("GET", f"/databases/{_notion_id(database_id)}")
        return parent, schema.get("properties", {})

    raise EnvironmentError(
        "Set NOTION_HANDOFF_DATA_SOURCE_ID or NOTION_HANDOFF_DATABASE_ID."
    )


def _multi_select_options(value: str) -> list[dict[str, str]]:
    parts = [part.strip() for part in re.split(r"[,、\n]", value) if part.strip()]
    return [{"name": part} for part in parts]


def build_property_value(field: str, value: str, schema: dict[str, Any]) -> dict[str, Any] | None:
    if not value:
        return None

    prop_type = schema.get(field, {}).get("type") or DEFAULT_PROPERTY_TYPES.get(field, "rich_text")
    if prop_type == "title":
        return {"title": _rich_text(value)}
    if prop_type == "rich_text":
        return {"rich_text": _rich_text(value)}
    if prop_type == "select":
        return {"select": {"name": value}}
    if prop_type == "multi_select":
        return {"multi_select": _multi_select_options(value)}
    if prop_type == "checkbox":
        return {"checkbox": value.strip().lower() in {"true", "yes", "1", "on"}}
    if prop_type == "number":
        try:
            number = float(value) if "." in value else int(value)
        except ValueError:
            return None
        return {"number": number}
    if prop_type == "url":
        return {"url": value}
    return {"rich_text": _rich_text(value)}


def build_critical_scope_information(fields: dict[str, str]) -> str:
    lines = ["## Critical Scope Information", ""]
    for field in V2_SCOPE_FIELDS:
        value = fields.get(field, "").strip()
        if value:
            value = re.sub(r"^\\\-", "-", value, flags=re.MULTILINE)
            lines.extend([f"{field}:", value, ""])
    if len(lines) == 2:
        return ""
    return "\n".join(lines).strip()


def build_notes_value(fields: dict[str, str]) -> str:
    notes = fields.get("Notes", "").strip()
    critical_scope = build_critical_scope_information(fields)
    if critical_scope and notes:
        return f"{critical_scope}\n\n{notes}"
    return critical_scope or notes


def build_properties(fields: dict[str, str], schema: dict[str, Any], title: str | None) -> dict[str, Any]:
    normalized = dict(fields)
    normalized["Task"] = title or fields.get("Task", "")
    normalized["Status"] = fields.get("Status") or "Ready"
    normalized["Notes"] = build_notes_value(fields)

    properties: dict[str, Any] = {}
    for field in PROPERTY_FIELDS:
        if field not in schema and field not in DEFAULT_PROPERTY_TYPES:
            continue
        prop_value = build_property_value(field, normalized.get(field, ""), schema)
        if prop_value is not None:
            properties[field] = prop_value
    return properties


def _paragraph_block(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": _rich_text(text)},
    }


def _heading_block(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": _rich_text(text)},
    }


def build_body_blocks(raw_log: str) -> list[dict[str, Any]]:
    if not raw_log:
        return []

    blocks = [
        _heading_block("Raw Log"),
    ]
    blocks.extend(_paragraph_block(chunk) for chunk in _split_text(raw_log))
    return blocks


def append_children(page_id: str, blocks: list[dict[str, Any]]) -> None:
    for start in range(0, len(blocks), APPEND_BATCH_SIZE):
        batch = blocks[start : start + APPEND_BATCH_SIZE]
        _request(
            "PATCH",
            f"/blocks/{_notion_id(page_id)}/children",
            {"children": batch},
        )


def create_handoff_page(fields: dict[str, str], title: str | None = None) -> dict[str, Any]:
    validate_fields(fields, title)
    parent, schema = get_parent()
    properties = build_properties(fields, schema, title)
    page = _request(
        "POST",
        "/pages",
        {
            "parent": parent,
            "properties": properties,
        },
    )

    append_children(page["id"], build_body_blocks(fields.get("Raw Log", "")))
    return page


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an AI Handoff Notion page from a labeled Markdown file.",
    )
    parser.add_argument("--from-file", required=True, help="Input Markdown file path.")
    parser.add_argument("--title", help="Override the Task title.")
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    input_path = Path(args.from_file)
    fields = parse_labeled_markdown(input_path.read_text(encoding="utf-8"))
    page = create_handoff_page(fields, title=args.title)
    page_id = page["id"]
    url = page.get("url", "")

    print("Created AI Handoff page")
    print(f"Page ID: {page_id}")
    print(f"URL: {url}")
    print("Next:")
    print(f"python relay\\generate_handoff_prompt.py --page-id {page_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HandoffInputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
