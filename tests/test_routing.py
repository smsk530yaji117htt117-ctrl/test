# -*- coding: utf-8 -*-
"""
会議 → Handoff 自動接続（型判定ルーティング）のテスト

対象: meeting_result_processor / relay.generate_handoff_prompt / relay.create_handoff_page
追加依存なし（標準ライブラリ + pytest のみ）。Notion へは書き込まない（dry_run）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from meeting_result_processor import (
    ROUTER_RULES,
    parse_synthesis,
    plan_actions,
    route_meeting_result,
)
from relay.generate_handoff_prompt import build_handoff_spec
from relay.create_handoff_page import build_notion_payload, create_handoff_page


def _synthesis(primary, secondary="なし", hrr="false", next_route=None):
    nr = next_route if next_route is not None else ROUTER_RULES.get(primary, "no_action")
    return (
        "### 結論\nこれが結論です。\n"
        "### 根拠\n根拠1\n根拠2\n"
        "### リスク\nリスク1\n"
        "### 推奨アクション\nアクション1\n"
        f"### タイプ判定\nprimary: {primary}\nsecondary: {secondary}\n"
        "### 推奨成果物\n成果物\n"
        f"### Human Review Required\n{hrr}\n"
        f"### Next Route\n{nr}\n"
    )


# ── 解析 ────────────────────────────────────────────────────────────────────

def test_parse_basic_dev_task():
    d = parse_synthesis(_synthesis("dev_task"))
    assert d.primary_type == "dev_task"
    assert d.secondary_types == []
    assert d.next_route == "create_handoff"
    assert d.human_review_required is False
    assert d.conclusion.startswith("これが結論")


def test_parse_secondary_and_fullwidth_colon():
    text = _synthesis("dev_task", secondary="doc_task").replace("primary:", "primary：")
    d = parse_synthesis(text)
    assert d.primary_type == "dev_task"
    assert "doc_task" in d.secondary_types


def test_parse_hrr_default_true_when_ambiguous():
    text = _synthesis("dev_task", hrr="（不明）")
    d = parse_synthesis(text)
    assert d.human_review_required is True  # 安全側


def test_parse_route_derived_from_type_when_missing():
    # Next Route に無効値を入れても primary から導出される
    d = parse_synthesis(_synthesis("research", next_route="???"))
    assert d.next_route == "research_more"


# ── ルート計画 ────────────────────────────────────────────────────────────────

def test_plan_dev_task_creates_handoff():
    actions = plan_actions(parse_synthesis(_synthesis("dev_task")))
    assert len(actions) == 1
    assert actions[0].route == "create_handoff"
    assert actions[0].spec["execution_mode"] == "Claude Code"


def test_plan_decision_is_no_action():
    actions = plan_actions(parse_synthesis(_synthesis("decision")))
    assert len(actions) == 1
    assert actions[0].route == "no_action"
    assert actions[0].spec is None  # 起票しない


def test_plan_research_prefixes_title_and_deep_research():
    actions = plan_actions(parse_synthesis(_synthesis("research")))
    assert actions[0].route == "research_more"
    assert actions[0].spec["task_title"].startswith("深掘り: ")
    assert actions[0].spec["execution_mode"] == "Deep Research"


def test_plan_doc_task_single_is_separate_loop():
    actions = plan_actions(parse_synthesis(_synthesis("doc_task")))
    assert actions[0].route == "create_doc"
    assert actions[0].role == "single"


def test_plan_composite_parent_and_two_children_doc_then_dev():
    d = parse_synthesis(_synthesis("dev_task", secondary="doc_task"))
    actions = plan_actions(d)
    assert [a.role for a in actions] == ["parent", "child", "child"]
    # 実行順 doc → dev
    assert actions[1].task_type == "doc_task"
    assert actions[2].task_type == "dev_task"


# ── human_review_required → Status ─────────────────────────────────────────────

def test_hrr_true_sets_status_draft():
    spec = build_handoff_spec(parse_synthesis(_synthesis("dev_task", hrr="true")),
                              task_type="dev_task")
    assert spec["status"] == "Draft"


def test_hrr_false_sets_status_ready():
    spec = build_handoff_spec(parse_synthesis(_synthesis("dev_task", hrr="false")),
                              task_type="dev_task")
    assert spec["status"] == "Ready"


# ── 起票（dry-run / 別ループ / no_action）────────────────────────────────────────

def test_route_dry_run_does_not_write_and_returns_payload():
    res = route_meeting_result(_synthesis("dev_task"), source_url="https://notion/x",
                               dry_run=True)
    assert res.dry_run is True
    created = res.actions[0].created
    assert created["dry_run"] is True
    assert created["payload"]["properties"]["Status"]["select"]["name"] == "Ready"


def test_route_standalone_doc_task_not_created_in_consensus_loop():
    res = route_meeting_result(_synthesis("doc_task"), dry_run=True)
    # doc_task 単独は合議ループからは起票しない（別ループ）
    assert res.actions[0].created is None


def test_route_no_action_not_created():
    res = route_meeting_result(_synthesis("decision"), dry_run=True)
    assert res.actions[0].route == "no_action"
    assert res.actions[0].created is None


def test_route_composite_creates_children():
    res = route_meeting_result(_synthesis("dev_task", secondary="doc_task"), dry_run=True)
    created = [a for a in res.actions if a.created is not None]
    # 親(create_handoff) + 子doc(create_doc,child) + 子dev(create_handoff) = 3件起票
    assert len(created) == 3


def test_route_uses_custom_creator():
    calls = []

    def fake_creator(spec, *, dry_run=False):
        calls.append(spec["task_title"])
        return {"ok": True}

    route_meeting_result(_synthesis("dev_task"), dry_run=False, handoff_creator=fake_creator)
    assert len(calls) == 1


# ── Notion payload 組み立て ────────────────────────────────────────────────────

def test_build_notion_payload_minimal_props():
    spec = build_handoff_spec(parse_synthesis(_synthesis("dev_task")), task_type="dev_task")
    payload = build_notion_payload(spec, "db123")
    props = payload["properties"]
    assert payload["parent"]["database_id"] == "db123"
    assert set(props).issubset(
        {"Task", "Status", "Task Type", "Execution Mode", "Notes"}
    )
    assert props["Task Type"]["select"]["name"] == "実装"


def test_create_handoff_page_dry_run_no_token_needed():
    spec = build_handoff_spec(parse_synthesis(_synthesis("dev_task")), task_type="dev_task")
    out = create_handoff_page(spec, dry_run=True, database_id="db123")
    assert out["dry_run"] is True
