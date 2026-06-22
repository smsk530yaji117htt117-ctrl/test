# -*- coding: utf-8 -*-
"""
⑥ live化カナリア前裁き: 会議→Handoff 自動ルーティングを live(dry_run=False) にしても
安全であることを担保する adversarial テスト。

既存の test_routing* / test_routing_guard が「正常系のルート判定」と「dedup」を覆うのに対し、
本ファイルは **live で誤起票しない不変条件** に絞る:
  - 壊れた/空の Synthesis では1件も起票しない（誤起票ゼロ）
  - decision / unknown は no_action（人間提示）で起票しない
  - HRR=true は live でも Draft（人間ゲートを維持。自動で Ready にしない）
  - 同一 run 内の同一 synthesis は二重起票しない
  - dedup 登録簿は in-process（別 run=別 store では効かない）→ cross-run は try_claim_page が守る、
    という設計上の限界を明示的に固定する
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from meeting_result_processor import route_meeting_result


def _synth(primary="dev_task", *, hrr="false", route="create_handoff", secondary="なし"):
    return (
        "### 結論\nテスト\n"
        "### 根拠\n-\n### リスク\n-\n### 推奨アクション\n-\n"
        f"### タイプ判定\nprimary: {primary}\nsecondary: {secondary}\n"
        "### 推奨成果物\n-\n"
        f"### Human Review Required\n{hrr}\n"
        f"### Next Route\n{route}\n"
    )


def _counter():
    calls = []

    def creator(spec, dry_run=True):
        calls.append(spec)
        return {"id": "x", "dry_run": dry_run}

    return calls, creator


# ── 誤起票ゼロ（壊れた入力で live でも何も起票しない）─────────────────────────────
def test_empty_synthesis_files_nothing_in_live():
    calls, creator = _counter()
    res = route_meeting_result("", dry_run=False, handoff_creator=creator, dedup_store=set())
    assert calls == []
    assert not any(getattr(a, "created", None) for a in res.actions)


def test_garbage_synthesis_files_nothing_in_live():
    calls, creator = _counter()
    route_meeting_result("これは型判定のない雑談テキストです。",
                         dry_run=False, handoff_creator=creator, dedup_store=set())
    assert calls == []


def test_decision_type_is_no_action_in_live():
    calls, creator = _counter()
    route_meeting_result(_synth("decision", route="no_action"),
                         dry_run=False, handoff_creator=creator, dedup_store=set())
    assert calls == []


# ── HRR=true は live でも Draft（人間ゲート維持）─────────────────────────────────
def test_hrr_true_stays_draft_in_live():
    calls, creator = _counter()
    route_meeting_result(_synth("dev_task", hrr="true"),
                         dry_run=False, handoff_creator=creator, dedup_store=set())
    assert len(calls) == 1
    assert calls[0]["status"] == "Draft"  # 自動で Ready にしない


def test_hrr_false_is_ready_in_live():
    calls, creator = _counter()
    route_meeting_result(_synth("dev_task", hrr="false"),
                         dry_run=False, handoff_creator=creator, dedup_store=set())
    assert len(calls) == 1
    assert calls[0]["status"] == "Ready"


# ── 二重起票防止（同一 run 内）────────────────────────────────────────────────
def test_same_synthesis_filed_once_per_run():
    store = set()
    text = _synth("dev_task", hrr="false")
    calls, creator = _counter()
    route_meeting_result(text, source_url="u1", dry_run=False, handoff_creator=creator, dedup_store=store)
    res2 = route_meeting_result(text, source_url="u1", dry_run=False, handoff_creator=creator, dedup_store=store)
    assert len(calls) == 1
    assert any(a.skipped for a in res2.actions)


# ── 設計限界の固定: in-process dedup は別 run（別 store）では効かない ───────────────
def test_dedup_is_in_process_only_cross_run_relies_on_claim_guard():
    text = _synth("dev_task", hrr="false")
    calls, creator = _counter()
    # 別 run を模して毎回新しい store を渡す → 二重防止は効かない（=想定どおり）
    route_meeting_result(text, source_url="u1", dry_run=False, handoff_creator=creator, dedup_store=set())
    route_meeting_result(text, source_url="u1", dry_run=False, handoff_creator=creator, dedup_store=set())
    assert len(calls) == 2  # cross-run の重複は consensus.try_claim_page（Status ロック）が守る
