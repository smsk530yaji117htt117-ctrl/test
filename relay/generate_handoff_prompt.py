#!/usr/bin/env python
"""Generate a GPT/Codex handoff prompt from a Notion AI Handoff page."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from notion_utils import get_page  # noqa: E402
from relay.prompt_templates import build_gpt_handoff_prompt  # noqa: E402

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> bool:
        return False


HANDOFF_FIELDS = [
    "Task",
    "Status",
    "From AI",
    "To AI",
    "Repository",
    "Branch",
    "Goal",
    "Current State",
    "Next Action",
    "Touched Files",
    "Do Not Touch",
    "Risks",
    "Commands Run",
    "Notes",
]


def _plain_text(items: list[dict[str, Any]]) -> str:
    return "".join(item.get("plain_text", "") for item in items).strip()


def _extract_property(prop: dict[str, Any]) -> str:
    prop_type = prop.get("type")
    if prop_type == "title":
        return _plain_text(prop.get("title", []))
    if prop_type == "rich_text":
        return _plain_text(prop.get("rich_text", []))
    if prop_type == "select":
        selected = prop.get("select")
        return selected.get("name", "") if selected else ""
    if prop_type == "multi_select":
        return ", ".join(item.get("name", "") for item in prop.get("multi_select", []))
    if prop_type == "date":
        date_value = prop.get("date")
        return date_value.get("start", "") if date_value else ""
    if prop_type == "url":
        return prop.get("url") or ""
    if prop_type == "email":
        return prop.get("email") or ""
    if prop_type == "phone_number":
        return prop.get("phone_number") or ""
    if prop_type == "checkbox":
        return "true" if prop.get("checkbox") else "false"
    if prop_type == "number":
        number = prop.get("number")
        return "" if number is None else str(number)
    return ""


def normalize_handoff_page(page: dict[str, Any]) -> dict[str, str]:
    properties = page.get("properties", {})
    fields: dict[str, str] = {}
    for field in HANDOFF_FIELDS:
        prop = properties.get(field)
        fields[field] = _extract_property(prop) if prop else ""
    return fields


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a GPT/Codex handoff prompt from a Notion AI Handoff page.",
    )
    parser.add_argument(
        "--page-id",
        required=True,
        help="Notion page ID for one row in the AI Handoff database.",
    )
    parser.add_argument(
        "--output",
        help="Optional output path. Defaults to stdout.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    if not os.environ.get("NOTION_TOKEN"):
        print("ERROR: NOTION_TOKEN is not set.", file=sys.stderr)
        return 2

    page = get_page(args.page_id)
    fields = normalize_handoff_page(page)
    prompt = build_gpt_handoff_prompt(fields)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(prompt, encoding="utf-8")
        print(f"Wrote handoff prompt: {output_path}")
    else:
        print(prompt)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
