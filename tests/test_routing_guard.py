# -*- coding: utf-8 -*-
"""
二重起票防止ガードのテスト（requirement 1）

同一 synthesis 結果（＋起票元 source_url）から会議/Handoff を二重に起票しないこと、
既存の重複防止フラグ（consensus.py の Status ベース楽観ロック）と整合する多層防御
として働くことを検証する。Notion へは書き込まない（fake creator / dry_run）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from meeting_result_processor import (
    ROUTER_RULES,
    _synthesis_fingerprint,
    reset_dedup_registry,
    route_meeting_result,
)


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


def _counting_creator():
    calls = []

    def creator(spec, *, dry_run=False):
        calls.append(spec["task_title"])
        return {"ok": True, "title": spec["task_title"]}

    return creator, calls


# ── 基本: 同一 synthesis は2回目以降 skip ─────────────────────────────────────

def test_second_call_same_synthesis_is_skipped():
    creator, calls = _counting_creator()
    store: set[str] = set()
    text = _synthesis("dev_task")

    first = route_meeting_result(text, dry_run=False, handoff_creator=creator,
                                 dedup_store=store)
    second = route_meeting_result(text, dry_run=False, handoff_creator=creator,
                                  dedup_store=store)

    # 起票は初回の1回だけ。2回目は handoff_creator を呼ばない。
    assert len(calls) == 1
    assert first.actions[0].created == {"ok": True, "title": calls[0]}
    assert first.actions[0].skipped is False
    # 2回目は skip され created は付かない
    assert second.actions[0].created is None
    assert second.actions[0].skipped is True
    assert "二重起票" in second.actions[0].note


# ── source_url が違えば別物として扱う ─────────────────────────────────────────

def test_different_source_url_is_not_deduped():
    creator, calls = _counting_creator()
    store: set[str] = set()
    text = _synthesis("dev_task")

    route_meeting_result(text, source_url="https://notion/a", dry_run=False,
                         handoff_creator=creator, dedup_store=store)
    route_meeting_result(text, source_url="https://notion/b", dry_run=False,
                         handoff_creator=creator, dedup_store=store)

    # 起票元が異なるので2回とも起票される
    assert len(calls) == 2


# ── 複合（親1+子2）も synthesis 単位で一括 skip ───────────────────────────────

def test_composite_children_skipped_on_second_call():
    creator, calls = _counting_creator()
    store: set[str] = set()
    text = _synthesis("dev_task", secondary="doc_task")

    first = route_meeting_result(text, dry_run=False, handoff_creator=creator,
                                 dedup_store=store)
    second = route_meeting_result(text, dry_run=False, handoff_creator=creator,
                                  dedup_store=store)

    created_first = [a for a in first.actions if a.created is not None]
    skipped_second = [a for a in second.actions if a.skipped]
    # 初回は 親+子doc+子dev の3件起票、2回目は同じ3件すべて skip
    assert len(created_first) == 3
    assert len(calls) == 3
    assert len(skipped_second) == 3
    assert all(a.created is None for a in second.actions)


# ── dry-run でも「起票（payload 生成）」は二重に行わない ────────────────────────

def test_dry_run_also_deduped():
    store: set[str] = set()
    text = _synthesis("dev_task")

    first = route_meeting_result(text, dry_run=True, dedup_store=store)
    second = route_meeting_result(text, dry_run=True, dedup_store=store)

    assert first.actions[0].created is not None
    assert first.actions[0].created["dry_run"] is True
    assert second.actions[0].created is None
    assert second.actions[0].skipped is True


# ── 起票しないルート（no_action）は登録簿を汚さない ───────────────────────────

def test_no_action_does_not_register_fingerprint():
    store: set[str] = set()
    route_meeting_result(_synthesis("decision"), dry_run=True, dedup_store=store)
    # 起票が一度も発生していないので登録簿は空のまま
    assert store == set()


# ── 既定登録簿（プロセス内）でもガードが効く ──────────────────────────────────

def test_default_registry_guards_and_reset_clears_it():
    reset_dedup_registry()
    creator, calls = _counting_creator()
    # 他テストと衝突しない一意な内容（source_url を一意化）
    text = _synthesis("dev_task")
    url = "https://notion/default-registry-guard-unique"

    route_meeting_result(text, source_url=url, dry_run=False, handoff_creator=creator)
    route_meeting_result(text, source_url=url, dry_run=False, handoff_creator=creator)
    assert len(calls) == 1  # 既定登録簿でも2回目は skip

    # reset で登録簿がクリアされ、再度起票できる
    reset_dedup_registry()
    route_meeting_result(text, source_url=url, dry_run=False, handoff_creator=creator)
    assert len(calls) == 2


# ── 空白ゆらぎは同一指紋に寄せる ──────────────────────────────────────────────

def test_fingerprint_normalizes_whitespace():
    a = _synthesis("dev_task")
    b = a + "\n\n   \n"  # 末尾の空白・改行ゆらぎ
    assert _synthesis_fingerprint(a) == _synthesis_fingerprint(b)
    # source_url が違えば指紋も違う
    assert _synthesis_fingerprint(a) != _synthesis_fingerprint(a, "https://x")
