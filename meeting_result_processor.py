#!/usr/bin/env python
"""Turn one completed AI Consensus Log result into a reviewable handoff draft."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> bool:
        return False

from notion_utils import get_page


REPOSITORY = r"C:\Users\smsk5\Documents\personal_os_consensus"
DO_NOT_TOUCH = (
    ".env",
    "API keys, tokens, or credentials",
    "Notion schema",
    "Render settings",
    "GitHub Settings",
    "GitHub Secrets",
    "GitHub Actions settings",
    "Billing",
    "git push",
    "PR merge",
    "production deletion",
    r"C:\Users\smsk5\deep_research.py",
    r"C:\Users\smsk5\dispatcher.py",
    r"C:\Users\smsk5\dispatcher_log.txt",
)

DEV_TERMS = {
    "implementation work is proposed": (
        "実装",
        "コード変更",
        "スクリプト作成",
        "スクリプトを",
        "テスト",
        "handoff",
        "relay",
        "router v1",
        "select_ai",
        "fallback prompt",
        "開発タスク",
    ),
}
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
    re.compile(r"\bntn_[A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
    re.compile(r"\bsecret_[A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
    re.compile(
        r"(?i)\b((?:(?:[a-z][a-z0-9_]*_)?(?:api[_ -]?key|token|secret)|"
        r"notion[_ -]?(?:secret|token|api[_ -]?key)|access[_ -]?token|"
        r"auth[_ -]?token)\s*[:=]\s*)([^\s,;]+)"
    ),
    re.compile(r"(?i)\b(bearer\s+)([A-Za-z0-9._-]{8,})"),
)
RESEARCH_TERMS = {
    "research or design investigation is the main action": (
        "調査",
        "比較",
        "設計検討",
        "情報収集",
        "リサーチ",
        "research",
        "検証のみ",
    ),
}
REVIEW_TERMS = {
    "human decision or approval is requested": (
        "人間判断",
        "人間承認",
        "承認が必要",
        "承認を",
        "権限判断",
        "費用判断",
        "リスク判断",
        "判断してください",
    ),
}
NO_ACTION_TERMS = {
    "the result is informational or already closed": (
        "完了済み",
        "対応済み",
        "次アクションなし",
        "no action",
        "記録のみ",
        "参考情報のみ",
        "雑談",
    ),
}
PROTECTED_TERMS = {
    "possible Notion schema change": (
        "notionスキーマ",
        "notion スキーマ",
        "notion schema",
        "notion dbフィールド",
        "フィールド追加",
        "attempt_count",
        "fallback_triggered",
    ),
    "secret or environment configuration": (
        ".env",
        "apiキー",
        "api key",
        "github secrets",
        "secret",
    ),
    "production or hosting configuration": (
        "render設定",
        "render settings",
        "render config",
        "本番削除",
        "production deletion",
    ),
    "privileged repository or billing operation": (
        "pr merge",
        "prマージ",
        "pr自動マージ",
        "github settings",
        "github actions",
        "billing",
        "課金",
    ),
    "automatic execution requires a safety decision": (
        "完全自動",
        "自動実行",
    ),
}


@dataclass(frozen=True)
class MeetingRecord:
    page_id: str
    title: str
    status: str
    text: str
    url: str = ""


@dataclass(frozen=True)
class ClassificationResult:
    classification: str
    human_review_required: bool
    reasons: tuple[str, ...]
    protected_matches: tuple[str, ...] = ()


def _configure_console() -> None:
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except AttributeError:
                pass


def _plain_text(items: list[dict[str, Any]]) -> str:
    return "".join(item.get("plain_text", "") for item in items).strip()


def _property_text(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    prop_type = prop.get("type")
    if prop_type == "title":
        return _plain_text(prop.get("title", []))
    if prop_type == "rich_text":
        return _plain_text(prop.get("rich_text", []))
    if prop_type == "select":
        value = prop.get("select")
        return value.get("name", "") if value else ""
    if prop_type == "multi_select":
        return ", ".join(value.get("name", "") for value in prop.get("multi_select", []))
    if prop_type == "url":
        return prop.get("url") or ""
    if prop_type == "checkbox":
        return "true" if prop.get("checkbox") else "false"
    return ""


def _first_property(properties: dict[str, Any], names: Iterable[str]) -> str:
    for name in names:
        value = _property_text(properties.get(name))
        if value:
            return value
    return ""


def read_meeting_record(page_id: str) -> MeetingRecord:
    """Read one AI Consensus Log row without changing its status or schema."""
    page = get_page(page_id)
    properties = page.get("properties", {})
    title = _first_property(properties, ("Question", "Task", "Title", "Name")) or "(untitled meeting result)"
    status = _property_text(properties.get("Status"))
    parts = []
    for field in ("Synthesis", "Claude_Response", "Gemini_Response", "GPT_Response"):
        value = _property_text(properties.get(field))
        if value:
            parts.append(f"{field}:\n{value}")
    text = "\n\n".join(parts) or title
    return MeetingRecord(
        page_id=page.get("id", page_id),
        title=title,
        status=status,
        text=text,
        url=page.get("url", ""),
    )


def _matched_labels(text: str, rules: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    normalized = text.casefold()
    return tuple(
        label
        for label, terms in rules.items()
        if any(term.casefold() in normalized for term in terms)
    )


def redact_sensitive_text(text: str) -> str:
    """Redact secret-like values before a meeting-derived value is emitted."""
    redacted = text
    for index, pattern in enumerate(SECRET_PATTERNS):
        if index < 3:
            redacted = pattern.sub("[REDACTED]", redacted)
        else:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
    return redacted


def _short_safe_text(text: str, limit: int = 240) -> str:
    compact = " ".join(redact_sensitive_text(text).split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def classify_meeting(title: str, text: str, status: str = "Complete") -> ClassificationResult:
    """Classify a completed meeting result while preserving safety review signals."""
    normalized_status = status.strip()
    if normalized_status.casefold() != "complete":
        displayed_status = normalized_status or "(missing)"
        return ClassificationResult(
            "no_action",
            False,
            (f"Status is {displayed_status!r}; only Complete meeting results are processed.",),
        )

    corpus = f"{title}\n{text}"
    dev_matches = _matched_labels(corpus, DEV_TERMS)
    research_matches = _matched_labels(corpus, RESEARCH_TERMS)
    review_matches = _matched_labels(corpus, REVIEW_TERMS)
    no_action_matches = _matched_labels(corpus, NO_ACTION_TERMS)
    protected_matches = _matched_labels(corpus, PROTECTED_TERMS)

    if dev_matches:
        reasons = list(dev_matches)
        if protected_matches:
            reasons.extend(protected_matches)
            reasons.append("implementation may proceed only after human approval")
        elif review_matches:
            reasons.extend(review_matches)
            reasons.append("implementation has an explicit human approval gate")
        return ClassificationResult(
            "dev_task",
            bool(protected_matches or review_matches),
            tuple(reasons),
            protected_matches,
        )

    if protected_matches or review_matches:
        return ClassificationResult(
            "human_review",
            True,
            tuple(protected_matches + review_matches),
            protected_matches,
        )

    if research_matches:
        return ClassificationResult("research_task", False, research_matches)

    if no_action_matches:
        return ClassificationResult("no_action", False, no_action_matches)

    return ClassificationResult(
        "no_action",
        False,
        ("no actionable implementation, investigation, or approval request was identified",),
    )


def _bullet_lines(values: Iterable[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


def _safe_raw_log(record: MeetingRecord) -> str:
    """Keep traceability without copying potentially sensitive meeting prose."""
    return (
        f"Source Page ID: {redact_sensitive_text(record.page_id)}\n"
        f"Source Title: {_short_safe_text(record.title)}\n"
        f"Source Status: {redact_sensitive_text(record.status)}\n\n"
        "Meeting content omitted from generated handoff output to prevent secret disclosure."
    )


def build_handoff_markdown(
    record: MeetingRecord,
    result: ClassificationResult,
    task_title: str | None = None,
) -> str:
    """Build the labeled v2 form consumed by relay/create_handoff_page.py."""
    if result.classification != "dev_task":
        raise ValueError("Handoff v2 Markdown is generated only for dev_task results.")
    if record.status.strip().casefold() != "complete":
        raise ValueError("Handoff v2 Markdown is generated only for Complete meeting results.")

    status = "Draft"
    source_title = _short_safe_text(record.title)
    title = redact_sensitive_text(task_title) if task_title else f"Development follow-up: {source_title[:100]}"
    review_value = "true" if result.human_review_required else "false"
    reason_text = "; ".join(result.reasons)
    next_action = (
        "A human reviews the protected-scope signals and confirms concrete target files "
        "before authorizing any implementation."
        if result.human_review_required
        else "Confirm concrete target files from the source meeting result, then implement "
        "only that scoped development task and report verification results."
    )
    goal = (
        "Prepare a scoped development follow-up from the completed AI meeting result: "
        f"{source_title}"
    )
    target_files = (
        "To be confirmed from the source meeting result before implementation.",
    )
    acceptance_criteria = [
        f"Source page {redact_sensitive_text(record.page_id)} was explicitly Status: Complete when classified.",
        f"The handoff records classification={result.classification} and human_review_required={review_value}.",
        "Concrete editable files and implementation scope are confirmed before any code change begins.",
        "No Notion schema, secret, hosting, privileged repository, or production deletion action is performed without human approval.",
    ]
    if result.human_review_required:
        acceptance_criteria.append("Human approval is obtained before implementation proceeds.")
    else:
        acceptance_criteria.append("Scoped implementation verification is reported after completion.")

    risks = list(result.protected_matches) or [
        "No protected-scope signal matched automatically; review for implicit risks before implementation."
    ]
    if result.human_review_required:
        risks.append("Do not execute implementation or privileged changes until a human approves scope.")
    suggested_next_ai = (
        "Codex after a human confirms protected scope and concrete target files."
        if result.human_review_required
        else "Codex after concrete target files are confirmed from the meeting result."
    )

    fields = [
        ("Task", title),
        ("Status", status),
        ("Repository", REPOSITORY),
        ("Working Directory", REPOSITORY),
        ("Target Files", _bullet_lines(target_files)),
        (
            "Execution Environment",
            _bullet_lines(("Windows", "cmd / PowerShell", "Python", "Notion API", "Existing relay scripts")),
        ),
        ("Git Managed", "Yes"),
        ("Do Not Touch", _bullet_lines(DO_NOT_TOUCH)),
        ("Goal", goal),
        (
            "Current State",
            f"Source AI Consensus Log page: {redact_sensitive_text(record.page_id)}\n"
            f"Source title: {source_title}\n"
            f"Source status: {redact_sensitive_text(record.status)}\n"
            f"Classification: {result.classification}\n"
            f"Human review required: {review_value}\n"
            f"Reason: {reason_text}",
        ),
        ("Next Action", next_action),
        (
            "Acceptance Criteria",
            _bullet_lines(acceptance_criteria),
        ),
        (
            "Escalation Rule",
            _bullet_lines(
                (
                    "Stop if a Notion schema change is required.",
                    "Stop if .env contents or API keys must be displayed or changed.",
                    "Stop if Render settings, GitHub settings, secrets, actions, billing, git push, PR merge, or production deletion is required.",
                    "Stop if an edit outside Target Files is required.",
                    "Stop if the AI Consensus Log page cannot be read.",
                    "Stop if required Handoff v2 information cannot be filled.",
                    "Stop if classification and human_review_required conflict.",
                )
            ),
        ),
        (
            "Touched Files",
            "- None reported by the source meeting result.",
        ),
        ("Risks", _bullet_lines(risks)),
        (
            "Commands Run",
            _bullet_lines(
                (
                    "Generated by meeting_result_processor.py; record actual verification commands in the completion report.",
                    "Notion handoff creation and prompt generation are separate, explicit relay steps.",
                )
            ),
        ),
        ("From AI", "Codex"),
        ("To AI", "Codex"),
        (
            "Notes",
            "Human Review Required:\n"
            f"{review_value}\n\n"
            "Suggested Next AI:\n"
            f"{suggested_next_ai}\n\n"
            "AI-Ready Conditions:\n"
            "- Repository, working directory, environment, and stop rules are explicit.\n"
            "- Concrete target files must be confirmed from the source meeting result.\n"
            f"- Human approval required before implementation: {review_value}.\n"
            "- The existing relay stores v2 scope in Notes; no Notion schema field is added.\n\n"
            "Output Safety:\n"
            "- Meeting prose is omitted from Raw Log output; secret-like values are redacted.",
        ),
        ("Raw Log", _safe_raw_log(record)),
    ]
    body = ["# Handoff v2", ""]
    for label, value in fields:
        body.extend([f"{label}:", value, ""])
    return "\n".join(body).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify one completed AI Consensus Log page and generate a relay-compatible Handoff v2 draft.",
    )
    parser.add_argument("--page-id", required=True, help="AI Consensus Log Notion page ID.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print classification and any dev_task handoff draft; never writes to Notion.",
    )
    parser.add_argument(
        "--write-handoff",
        action="store_true",
        help="Write Handoff v2 Markdown to --output. This does not call the relay or write to Notion.",
    )
    parser.add_argument("--output", type=Path, help="Output path for generated Handoff v2 Markdown; required with --write-handoff.")
    parser.add_argument("--task-title", help="Override the generated Handoff Task value.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _configure_console()
    load_dotenv()
    args = parse_args(argv)

    if args.output and not (args.write_handoff or args.dry_run):
        print("ERROR: --output requires --write-handoff or --dry-run.", file=sys.stderr)
        return 2
    if args.write_handoff and not args.output:
        print("ERROR: --write-handoff requires --output to avoid creating files in the working directory.", file=sys.stderr)
        return 2
    if not os.environ.get("NOTION_TOKEN"):
        print("ERROR: NOTION_TOKEN is not set.", file=sys.stderr)
        return 2

    record = read_meeting_record(args.page_id)
    result = classify_meeting(record.title, record.text, record.status)
    print(
        json.dumps(
            {
                "page_id": record.page_id,
                "title": _short_safe_text(record.title),
                "status": redact_sensitive_text(record.status),
                "classification": result.classification,
                "human_review_required": result.human_review_required,
                "reasons": list(result.reasons),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if result.classification != "dev_task":
        if args.write_handoff or args.output:
            print("ERROR: Handoff v2 output is limited to dev_task results.", file=sys.stderr)
            return 2
        return 0

    markdown = build_handoff_markdown(record, result, args.task_title)
    should_write = args.output is not None
    if should_write:
        output = args.output
        output.write_text(markdown, encoding="utf-8")
        print(f"Wrote Handoff v2 Markdown: {output}")
    if args.dry_run or not should_write:
        print("\n--- Handoff v2 Markdown (relay-compatible draft) ---\n")
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
