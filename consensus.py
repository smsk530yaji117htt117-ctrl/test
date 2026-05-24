"""AI Meeting System consensus module (PersonalOS 1.3-beta extension).

Adds three features on top of the existing AI meeting consensus loop:

1. Synthesis output is normalized to 8 fixed Markdown sections.
2. Primary Type drives auto-creation of dev_task / doc_task Handoffs in the
   AI Handoff DB. Status is Draft when Human Review is required, Ready when
   not.
3. The AI Consensus Log "Handoff起票済み" checkbox prevents duplicate
   Handoff creation. The checkbox is flipped to true ONLY after the Handoff
   creation succeeds, so failed runs can safely retry.

Design spec: https://www.notion.so/36a5ae2b8d6a8183bf3cca892b34cd01

The module is intentionally I/O-thin: the Notion client is injected by the
caller so the orchestration is unit-testable without hitting Notion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Spec constants
# ---------------------------------------------------------------------------

PRIMARY_TYPES: frozenset[str] = frozenset({
    "dev_task",
    "doc_task",
    "decision",
    "research",
})

HANDOFF_TARGET_TYPES: frozenset[str] = frozenset({"dev_task", "doc_task"})

NEXT_ROUTES: frozenset[str] = frozenset({
    "create_handoff",
    "create_doc_draft",
    "request_human_decision",
    "research_more",
    "no_action",
})

SYNTHESIS_SECTIONS: tuple[str, ...] = (
    "結論",
    "根拠",
    "リスク",
    "推奨アクション",
    "タイプ判定",
    "推奨成果物",
    "Human Review Required",
    "Next Route",
)

HANDOFF_CREATED_PROP = "Handoff起票済み"


# ---------------------------------------------------------------------------
# Feature 1: 8-section Synthesis prompt
# ---------------------------------------------------------------------------

SYNTHESIS_PROMPT_TEMPLATE = """\
あなたはAI会議の議長である。以下の議論ログをもとに、最終Synthesis（合意結論）を作成せよ。

## 必須出力形式

以下8セクションのMarkdownで必ず出力すること。セクション順序および見出し名（##）は固定で、追加・削除・改名は禁止する。

## 結論
会議結果として採用する判断、最終方針、または合意内容を1-2文で簡潔に。

## 根拠
判断に使った理由、合議結果、前提、制約、代替案との比較。箇条書きで3点以内。

## リスク
実装、運用、外部API、権限、データ、レビュー上の懸念。箇条書きで2点以内。

## 推奨アクション
次に取るべき具体アクションを1-3件。Handoff化、資料化、調査、人間判断など。

## タイプ判定
Primary Type: <dev_task | doc_task | decision | research のいずれか1つ>
Secondary Types: <該当タイプを複数列挙。なければ none>

## 推奨成果物
Handoff、Notionページ、仕様書、実装PR、調査メモなど。

## Human Review Required
<true | false>
実装投入前に人間承認が必須なら true。安全側に倒すこと。

## Next Route
<create_handoff | create_doc_draft | request_human_decision | research_more | no_action のいずれか1つ>

---

## 議論ログ
{meeting_input}
"""


def build_synthesis_prompt(meeting_input: str) -> str:
    """Build the Synthesis prompt with the meeting transcript embedded."""
    return SYNTHESIS_PROMPT_TEMPLATE.format(meeting_input=meeting_input)


# ---------------------------------------------------------------------------
# Feature 2 (a): Parse the Synthesis Markdown
# ---------------------------------------------------------------------------

_H2_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class SynthesisDecision:
    """Structured view of a parsed Synthesis."""

    primary_type: Optional[str]
    secondary_types: tuple[str, ...]
    human_review_required: bool
    next_route: Optional[str]
    sections: dict[str, str]

    @property
    def should_create_handoff(self) -> bool:
        return self.primary_type in HANDOFF_TARGET_TYPES


def parse_synthesis_sections(synthesis_text: str) -> dict[str, str]:
    """Split a Synthesis Markdown into {section_name: body} pairs.

    Sections the model omits are simply absent from the result; the caller
    decides what to do. Body whitespace is stripped.
    """
    sections: dict[str, str] = {}
    matches = list(_H2_PATTERN.finditer(synthesis_text))
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(synthesis_text)
        sections[name] = synthesis_text[body_start:body_end].strip()
    return sections


def _extract_token_after(label: str, text: str, allowed: frozenset[str]) -> Optional[str]:
    """Find ``Label: token`` and return token only if it is in ``allowed``."""
    pattern = rf"{re.escape(label)}\s*\**\s*[:：]\s*([A-Za-z_]+)"
    m = re.search(pattern, text)
    if not m:
        return None
    token = m.group(1).strip().lower()
    return token if token in allowed else None


def _extract_secondary_types(text: str) -> tuple[str, ...]:
    m = re.search(r"Secondary Types?\s*\**\s*[:：]\s*(.+)", text)
    if not m:
        return ()
    raw = m.group(1).strip().lower()
    if not raw or raw == "none":
        return ()
    parts = re.split(r"[,、\s]+", raw)
    return tuple(p for p in parts if p in PRIMARY_TYPES)


def _extract_human_review_required(text: str) -> bool:
    """Default to True (safe) when ambiguous."""
    t = text.strip().lower()
    if re.search(r"\btrue\b", t):
        return True
    if re.search(r"\bfalse\b", t):
        return False
    return True


def _extract_next_route(text: str) -> Optional[str]:
    t = text.strip().lower()
    for route in NEXT_ROUTES:
        if re.search(rf"\b{re.escape(route)}\b", t):
            return route
    return None


def parse_synthesis_decision(synthesis_text: str) -> SynthesisDecision:
    """Build a SynthesisDecision from raw Synthesis Markdown."""
    sections = parse_synthesis_sections(synthesis_text)
    type_section = sections.get("タイプ判定", "")
    return SynthesisDecision(
        primary_type=_extract_token_after("Primary Type", type_section, PRIMARY_TYPES),
        secondary_types=_extract_secondary_types(type_section),
        human_review_required=_extract_human_review_required(
            sections.get("Human Review Required", "")
        ),
        next_route=_extract_next_route(sections.get("Next Route", "")),
        sections=sections,
    )


# ---------------------------------------------------------------------------
# Feature 2 (b): Build the Handoff DB row
# ---------------------------------------------------------------------------

_HANDOFF_TO_AI = {
    "dev_task": "Claude Code",
    "doc_task": "Claude",
}

# The AI Handoff DB Task Type select currently has a single shared option;
# the dev_task/doc_task distinction is carried in the Task title prefix and
# the Notes block.
_HANDOFF_TASK_TYPE_VALUE = "実装"


def _truncate(text: str, limit: int = 2000) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_handoff_properties(
    decision: SynthesisDecision,
    consensus_log_url: str,
    consensus_log_title: str,
) -> dict[str, Any]:
    """Build the ``properties`` dict for a new Notion AI Handoff DB page."""
    if decision.primary_type not in HANDOFF_TARGET_TYPES:
        raise ValueError(
            f"primary_type={decision.primary_type!r} is not a Handoff target"
        )

    status = "Draft" if decision.human_review_required else "Ready"
    task_title = f"[Auto/{decision.primary_type}] {consensus_log_title}"
    goal = decision.sections.get("結論", "").strip() or "(結論セクションなし)"
    secondary = ", ".join(decision.secondary_types) or "none"

    notes_lines = [
        f"自動起票元: {consensus_log_url}",
        f"Primary Type: {decision.primary_type}",
        f"Secondary Types: {secondary}",
        f"Next Route: {decision.next_route or 'unknown'}",
        "",
        "## 推奨アクション",
        decision.sections.get("推奨アクション", "(なし)"),
        "",
        "## リスク",
        decision.sections.get("リスク", "(なし)"),
    ]

    return {
        "Task": {"title": [{"text": {"content": _truncate(task_title, 200)}}]},
        "Task Type": {"select": {"name": _HANDOFF_TASK_TYPE_VALUE}},
        "Status": {"select": {"name": status}},
        "Human Review Required": {"checkbox": decision.human_review_required},
        "From AI": {"select": {"name": "Consensus"}},
        "To AI": {"select": {"name": _HANDOFF_TO_AI[decision.primary_type]}},
        "Goal": {"rich_text": [{"text": {"content": _truncate(goal)}}]},
        "Notes": {"rich_text": [{"text": {"content": _truncate("\n".join(notes_lines))}}]},
    }


# ---------------------------------------------------------------------------
# Feature 3: Duplicate prevention via Handoff起票済み
# ---------------------------------------------------------------------------

def is_handoff_already_created(notion_client: Any, consensus_log_page_id: str) -> bool:
    """Return True iff the log's Handoff起票済み checkbox is already true."""
    page = notion_client.pages.retrieve(consensus_log_page_id)
    prop = page.get("properties", {}).get(HANDOFF_CREATED_PROP, {})
    return bool(prop.get("checkbox", False))


def mark_handoff_created(notion_client: Any, consensus_log_page_id: str) -> None:
    """Flip Handoff起票済み to true.

    Per spec, call this ONLY after the Handoff page was successfully created.
    The checkbox is the sole durable signal that prevents re-issue, so an
    optimistic flip would silently drop work on the next run.
    """
    notion_client.pages.update(
        page_id=consensus_log_page_id,
        properties={HANDOFF_CREATED_PROP: {"checkbox": True}},
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProcessingResult:
    skipped: bool
    reason: Optional[str] = None
    primary_type: Optional[str] = None
    handoff_page_id: Optional[str] = None
    error: Optional[str] = None


def process_consensus_result(
    notion_client: Any,
    ai_handoff_db_id: str,
    consensus_log_page_id: str,
    consensus_log_url: str,
    consensus_log_title: str,
    synthesis_text: str,
) -> ProcessingResult:
    """Top-level 1.3-beta routing entry point.

    Order of operations (per spec):
      1. Skip if Handoff起票済み is already true.
      2. Parse Synthesis. Skip if Primary Type is not dev_task / doc_task.
      3. Create the Handoff page in AI Handoff DB.
      4. On success only, mark Handoff起票済み = true.

    The consensus meeting loop must not be destroyed by routing failures, so
    Notion errors are caught and reported via ``ProcessingResult.error``.
    """
    if is_handoff_already_created(notion_client, consensus_log_page_id):
        return ProcessingResult(skipped=True, reason="already_created")

    decision = parse_synthesis_decision(synthesis_text)

    if not decision.should_create_handoff:
        return ProcessingResult(
            skipped=True,
            reason=f"primary_type={decision.primary_type!r} not in target set",
            primary_type=decision.primary_type,
        )

    properties = build_handoff_properties(
        decision=decision,
        consensus_log_url=consensus_log_url,
        consensus_log_title=consensus_log_title,
    )
    try:
        page = notion_client.pages.create(
            parent={"database_id": ai_handoff_db_id},
            properties=properties,
        )
    except Exception as exc:  # noqa: BLE001 - documented orchestrator boundary
        return ProcessingResult(
            skipped=False,
            primary_type=decision.primary_type,
            error=f"{type(exc).__name__}: {exc}",
        )

    mark_handoff_created(notion_client, consensus_log_page_id)
    return ProcessingResult(
        skipped=False,
        primary_type=decision.primary_type,
        handoff_page_id=page.get("id"),
    )
