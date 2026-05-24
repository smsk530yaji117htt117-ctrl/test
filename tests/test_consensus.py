"""Tests for consensus.py (PersonalOS 1.3-beta extension).

Covers:
- Spec constants alignment.
- Synthesis section parsing and decision extraction.
- Handoff property construction (Status / Human Review / Task Type).
- Orchestrator paths: duplicate skip, non-target skip, success, failure.

These tests use a stub Notion client and do NOT hit the real Notion API.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from consensus import (  # noqa: E402
    HANDOFF_CREATED_PROP,
    HANDOFF_TARGET_TYPES,
    NEXT_ROUTES,
    PRIMARY_TYPES,
    SYNTHESIS_SECTIONS,
    build_handoff_properties,
    build_synthesis_prompt,
    is_handoff_already_created,
    mark_handoff_created,
    parse_synthesis_decision,
    parse_synthesis_sections,
    process_consensus_result,
)


# ---------------------------------------------------------------------------
# Sample Synthesis fixtures
# ---------------------------------------------------------------------------

SAMPLE_DEV_TASK = """## 結論
consensus.py を拡張し、Synthesis を 8 セクション構造に変更する。

## 根拠
- spec で 8 セクションが必須化された
- doc_task の方針が承認済み

## リスク
- Gemini の出力制限で truncation 発生の可能性

## 推奨アクション
- consensus.py の Synthesis プロンプトを差し替える
- パース層を追加する

## タイプ判定
Primary Type: dev_task
Secondary Types: doc_task

## 推奨成果物
PR (feature/1.3-beta-synthesis-routing)

## Human Review Required
false

## Next Route
create_handoff
"""

SAMPLE_DOC_TASK_REVIEW_REQUIRED = """## 結論
仕様資料を Notion ページ化する。

## 根拠
- 後続 dev_task が参照する一次資料が必要

## リスク
- 二重資料化のリスク

## 推奨アクション
- Notion ページに展開する

## タイプ判定
Primary Type: doc_task
Secondary Types: none

## 推奨成果物
Notion ページ

## Human Review Required
true

## Next Route
create_doc_draft
"""

SAMPLE_DECISION = """## 結論
方針 A を採用する。

## 根拠
- 単純である

## リスク
- 当面なし

## 推奨アクション
- 関係者に周知する

## タイプ判定
Primary Type: decision
Secondary Types: none

## 推奨成果物
決定記録ページ

## Human Review Required
true

## Next Route
request_human_decision
"""


# ---------------------------------------------------------------------------
# Stub Notion client
# ---------------------------------------------------------------------------

@dataclass
class StubPages:
    pages: dict[str, dict] = field(default_factory=dict)
    create_calls: list[dict] = field(default_factory=list)
    update_calls: list[dict] = field(default_factory=list)
    create_should_raise: Optional[Exception] = None
    next_page_id: str = "new-handoff-page-id"

    def retrieve(self, page_id: str) -> dict:
        return self.pages[page_id]

    def update(self, page_id: str, properties: dict) -> dict:
        self.update_calls.append({"page_id": page_id, "properties": properties})
        page = self.pages.setdefault(page_id, {"properties": {}})
        page.setdefault("properties", {}).update(properties)
        return page

    def create(self, parent: dict, properties: dict) -> dict:
        self.create_calls.append({"parent": parent, "properties": properties})
        if self.create_should_raise is not None:
            raise self.create_should_raise
        return {"id": self.next_page_id, "properties": properties}


@dataclass
class StubNotion:
    pages: StubPages = field(default_factory=StubPages)


def _seed_log(notion: StubNotion, log_id: str, already: bool = False) -> None:
    notion.pages.pages[log_id] = {
        "properties": {HANDOFF_CREATED_PROP: {"checkbox": already}},
    }


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_primary_types_match_spec():
    assert PRIMARY_TYPES == {"dev_task", "doc_task", "decision", "research"}


def test_handoff_target_types_match_spec():
    assert HANDOFF_TARGET_TYPES == {"dev_task", "doc_task"}


def test_next_routes_match_spec():
    assert NEXT_ROUTES == {
        "create_handoff",
        "create_doc_draft",
        "request_human_decision",
        "research_more",
        "no_action",
    }


def test_synthesis_sections_match_spec():
    assert SYNTHESIS_SECTIONS == (
        "結論",
        "根拠",
        "リスク",
        "推奨アクション",
        "タイプ判定",
        "推奨成果物",
        "Human Review Required",
        "Next Route",
    )


# ---------------------------------------------------------------------------
# Feature 1: prompt
# ---------------------------------------------------------------------------

def test_build_synthesis_prompt_contains_all_eight_section_headers():
    prompt = build_synthesis_prompt("dummy meeting log")
    for section in SYNTHESIS_SECTIONS:
        assert f"## {section}" in prompt
    assert "dummy meeting log" in prompt


# ---------------------------------------------------------------------------
# Feature 2 (a): parsing
# ---------------------------------------------------------------------------

def test_parse_synthesis_sections_returns_eight_sections():
    sections = parse_synthesis_sections(SAMPLE_DEV_TASK)
    assert set(sections) == set(SYNTHESIS_SECTIONS)


def test_parse_synthesis_decision_dev_task_path():
    d = parse_synthesis_decision(SAMPLE_DEV_TASK)
    assert d.primary_type == "dev_task"
    assert d.secondary_types == ("doc_task",)
    assert d.human_review_required is False
    assert d.next_route == "create_handoff"
    assert d.should_create_handoff is True


def test_parse_synthesis_decision_doc_task_review_required():
    d = parse_synthesis_decision(SAMPLE_DOC_TASK_REVIEW_REQUIRED)
    assert d.primary_type == "doc_task"
    assert d.secondary_types == ()
    assert d.human_review_required is True
    assert d.next_route == "create_doc_draft"
    assert d.should_create_handoff is True


def test_parse_synthesis_decision_decision_path_is_not_handoff_target():
    d = parse_synthesis_decision(SAMPLE_DECISION)
    assert d.primary_type == "decision"
    assert d.should_create_handoff is False
    assert d.next_route == "request_human_decision"


def test_unknown_primary_type_returns_none():
    text = "## タイプ判定\nPrimary Type: bogus\nSecondary Types: none\n"
    d = parse_synthesis_decision(text)
    assert d.primary_type is None
    assert d.should_create_handoff is False


def test_human_review_required_defaults_to_true_when_ambiguous():
    text = "## Human Review Required\n\n## Next Route\nno_action\n"
    d = parse_synthesis_decision(text)
    assert d.human_review_required is True


def test_full_width_colon_in_type_line_is_accepted():
    text = "## タイプ判定\nPrimary Type： dev_task\nSecondary Types： none\n"
    d = parse_synthesis_decision(text)
    assert d.primary_type == "dev_task"


# ---------------------------------------------------------------------------
# Feature 2 (b): Handoff properties
# ---------------------------------------------------------------------------

def test_build_handoff_properties_dev_task_ready_status():
    d = parse_synthesis_decision(SAMPLE_DEV_TASK)
    props = build_handoff_properties(
        d, "https://notion.so/log/abc", "Test Consensus Log"
    )
    assert props["Status"]["select"]["name"] == "Ready"
    assert props["Human Review Required"]["checkbox"] is False
    assert props["To AI"]["select"]["name"] == "Claude Code"
    assert props["From AI"]["select"]["name"] == "Consensus"
    title = props["Task"]["title"][0]["text"]["content"]
    assert title.startswith("[Auto/dev_task]")
    notes = props["Notes"]["rich_text"][0]["text"]["content"]
    assert "Primary Type: dev_task" in notes
    assert "Secondary Types: doc_task" in notes
    assert "https://notion.so/log/abc" in notes


def test_build_handoff_properties_doc_task_draft_when_review_required():
    d = parse_synthesis_decision(SAMPLE_DOC_TASK_REVIEW_REQUIRED)
    props = build_handoff_properties(d, "u", "DocLog")
    assert props["Status"]["select"]["name"] == "Draft"
    assert props["Human Review Required"]["checkbox"] is True
    assert props["To AI"]["select"]["name"] == "Claude"
    title = props["Task"]["title"][0]["text"]["content"]
    assert title.startswith("[Auto/doc_task]")


def test_build_handoff_properties_rejects_non_target_type():
    d = parse_synthesis_decision(SAMPLE_DECISION)
    with pytest.raises(ValueError):
        build_handoff_properties(d, "u", "t")


# ---------------------------------------------------------------------------
# Feature 3: duplicate guard
# ---------------------------------------------------------------------------

def test_is_handoff_already_created_true():
    n = StubNotion()
    _seed_log(n, "log-1", already=True)
    assert is_handoff_already_created(n, "log-1") is True


def test_is_handoff_already_created_false():
    n = StubNotion()
    _seed_log(n, "log-1", already=False)
    assert is_handoff_already_created(n, "log-1") is False


def test_mark_handoff_created_sets_checkbox_true():
    n = StubNotion()
    _seed_log(n, "log-1", already=False)
    mark_handoff_created(n, "log-1")
    assert n.pages.pages["log-1"]["properties"][HANDOFF_CREATED_PROP]["checkbox"] is True


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def test_orchestrator_skips_when_already_created():
    n = StubNotion()
    _seed_log(n, "log-1", already=True)
    result = process_consensus_result(
        n, "db-handoff", "log-1", "https://u", "title", SAMPLE_DEV_TASK
    )
    assert result.skipped
    assert result.reason == "already_created"
    assert n.pages.create_calls == []


def test_orchestrator_skips_when_primary_type_not_in_target():
    n = StubNotion()
    _seed_log(n, "log-1")
    result = process_consensus_result(
        n, "db-handoff", "log-1", "https://u", "title", SAMPLE_DECISION
    )
    assert result.skipped
    assert result.primary_type == "decision"
    assert n.pages.create_calls == []
    log = n.pages.pages["log-1"]
    assert log["properties"][HANDOFF_CREATED_PROP]["checkbox"] is False


def test_orchestrator_creates_handoff_and_marks_log():
    n = StubNotion()
    _seed_log(n, "log-1")
    n.pages.next_page_id = "new-handoff-1"
    result = process_consensus_result(
        n, "db-handoff", "log-1", "https://u", "title", SAMPLE_DEV_TASK
    )
    assert not result.skipped
    assert result.primary_type == "dev_task"
    assert result.handoff_page_id == "new-handoff-1"
    assert result.error is None
    assert len(n.pages.create_calls) == 1
    call = n.pages.create_calls[0]
    assert call["parent"] == {"database_id": "db-handoff"}
    log = n.pages.pages["log-1"]
    assert log["properties"][HANDOFF_CREATED_PROP]["checkbox"] is True


def test_orchestrator_doc_task_review_required_status_draft():
    n = StubNotion()
    _seed_log(n, "log-1")
    result = process_consensus_result(
        n, "db-handoff", "log-1", "https://u", "title",
        SAMPLE_DOC_TASK_REVIEW_REQUIRED,
    )
    assert not result.skipped
    assert result.primary_type == "doc_task"
    call = n.pages.create_calls[0]
    assert call["properties"]["Status"]["select"]["name"] == "Draft"


def test_orchestrator_does_not_mark_log_on_creation_failure():
    n = StubNotion()
    _seed_log(n, "log-1")
    n.pages.create_should_raise = RuntimeError("Notion 500")
    result = process_consensus_result(
        n, "db-handoff", "log-1", "https://u", "title", SAMPLE_DEV_TASK
    )
    assert not result.skipped
    assert result.error is not None
    assert "Notion 500" in result.error
    assert result.handoff_page_id is None
    log = n.pages.pages["log-1"]
    assert log["properties"][HANDOFF_CREATED_PROP]["checkbox"] is False
    assert n.pages.update_calls == []
