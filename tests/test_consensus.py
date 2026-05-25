"""Tests for consensus.py 1.3-beta — covers all Acceptance Criteria."""

import pytest
from consensus import (
    SYNTHESIS_SECTIONS,
    build_handoff_properties,
    build_synthesis_prompt,
    parse_synthesis_decision,
    parse_synthesis_sections,
    process_consensus_result,
)


def _synthesis(primary_type="dev_task", hrr="true", next_route="create_handoff"):
    return (
        f"## 結論\nテスト結論。\n\n## 根拠\n- 根拠A\n\n## リスク\n- リスクX\n\n"
        f"## 推奨アクション\n- アクション1\n\n## タイプ判定\nPrimary Type: {primary_type}\n"
        f"Secondary Types: none\n\n## 推奨成果物\nHandoff\n\n"
        f"## Human Review Required\n{hrr}\n\n## Next Route\n{next_route}\n"
    )


class _Notion:
    """Minimal Notion stub."""

    def __init__(self, already=False, fail=False):
        self._already = already
        self._fail = fail
        self.created = []
        self.marked = []

    @property
    def pages(self):
        return self

    def retrieve(self, _id):
        return {"properties": {"Handoff起票済み": {"checkbox": self._already}}}

    def create(self, parent, properties):
        if self._fail:
            raise RuntimeError("unavailable")
        p = {"id": "new-id", "properties": properties}
        self.created.append(p)
        return p

    def update(self, page_id, properties):
        self.marked.append(page_id)


# AC1: Synthesis 出力が構造化フォーマットになっている
def test_prompt_contains_all_8_sections():
    prompt = build_synthesis_prompt("ログ")
    for s in SYNTHESIS_SECTIONS:
        assert s in prompt


def test_parse_all_8_sections():
    assert set(parse_synthesis_sections(_synthesis())) >= set(SYNTHESIS_SECTIONS)


# AC2: primary_type に応じたルーティングが動作する
def test_dev_task_creates_handoff():
    dec = parse_synthesis_decision(_synthesis("dev_task", "false"))
    assert dec.should_create_handoff and dec.primary_type == "dev_task"
    props = build_handoff_properties(dec, "https://x.com", "T")
    assert props["Status"]["select"]["name"] == "Ready"


def test_doc_task_creates_draft_when_hrr_true():
    dec = parse_synthesis_decision(_synthesis("doc_task", "true"))
    props = build_handoff_properties(dec, "https://x.com", "T")
    assert props["Status"]["select"]["name"] == "Draft"


def test_decision_skips_handoff():
    dec = parse_synthesis_decision(_synthesis("decision"))
    assert not dec.should_create_handoff


def test_unknown_type_skipped():
    dec = parse_synthesis_decision(_synthesis("bogus"))
    assert dec.primary_type is None or not dec.should_create_handoff


# AC3: 既存の graceful degradation が維持されている
def test_notion_error_does_not_mark_checkbox():
    n = _Notion(fail=True)
    r = process_consensus_result(n, "db", "log", "https://x.com", "T", _synthesis())
    assert r.error is not None and n.marked == []


def test_already_created_is_skipped():
    n = _Notion(already=True)
    r = process_consensus_result(n, "db", "log", "https://x.com", "T", _synthesis())
    assert r.skipped and n.created == []


def test_successful_flow_marks_checkbox():
    n = _Notion()
    r = process_consensus_result(n, "db", "log", "https://x.com", "T", _synthesis())
    assert r.handoff_page_id == "new-id" and "log" in n.marked


def test_ambiguous_hrr_defaults_safe():
    text = _synthesis().replace("true", "unclear")
    assert parse_synthesis_decision(text).human_review_required is True
