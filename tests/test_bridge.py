# -*- coding: utf-8 -*-
"""bridge.py のテスト（Queue ポーリング / fire / notify ディスパッチ / SELFTEST）。"""
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import bridge_notion as bn
import bridge
from notify import NotifyResult


def _rt(text):
    return [{"plain_text": text}]


def make_row(page_id, action, target="", payload="", status="Pending", result="", name="n"):
    return {"id": page_id, "properties": {
        "Name": {"type": "title", "title": _rt(name)},
        "Action": {"type": "select", "select": {"name": action} if action else None},
        "Target": {"type": "rich_text", "rich_text": _rt(target)},
        "Payload": {"type": "rich_text", "rich_text": _rt(payload)},
        "Status": {"type": "select", "select": {"name": status}},
        "Result": {"type": "rich_text", "rich_text": _rt(result)},
    }}


@pytest.fixture(autouse=True)
def clean_fire_env(monkeypatch):
    for k in list(os.environ):
        if k.startswith("ROUTINE_FIRE_"):
            monkeypatch.delenv(k, raising=False)
    yield


# ─── fire ─────────────────────────────────────────────────────────────────────

def test_fire_success_records_session_url(monkeypatch):
    monkeypatch.setenv("ROUTINE_FIRE_URL_PR_SYNC", "https://api.anthropic.com/v1/routines/x")
    monkeypatch.setenv("ROUTINE_FIRE_TOKEN_PR_SYNC", "secret-token-123")
    captured = {}

    def fake_post(url, headers, payload, timeout=30):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return 200, {"claude_code_session_url": "https://claude.ai/code/session_abc"}

    with patch.object(bn, "http_post_json", side_effect=fake_post):
        status, result = bridge._do_fire("PR_SYNC", "go")

    assert status == "Done"
    assert "https://claude.ai/code/session_abc" in result
    assert captured["headers"]["anthropic-beta"] == bridge.ROUTINE_BETA_HEADER
    assert captured["headers"]["anthropic-version"] == bridge.ANTHROPIC_VERSION
    assert captured["headers"]["Authorization"].startswith("Bearer ")
    assert captured["payload"] == {"text": "go"}


def test_fire_env_missing(monkeypatch):
    status, result = bridge._do_fire("PR_SYNC", "go")
    assert status == "Error" and result == "env未設定"


def test_fire_empty_target():
    status, result = bridge._do_fire("", "go")
    assert status == "Error"


def test_fire_http_error_is_masked(monkeypatch):
    monkeypatch.setenv("ROUTINE_FIRE_URL_K", "https://api.anthropic.com/x")
    monkeypatch.setenv("ROUTINE_FIRE_TOKEN_K", "topsecretvalue123")
    with patch.object(bn, "http_post_json",
                      side_effect=bn.HttpError(401, "bad token topsecretvalue123")):
        status, result = bridge._do_fire("K", "go")
    assert status == "Error"
    assert "topsecretvalue123" not in result


# ─── notify ディスパッチ ──────────────────────────────────────────────────────

def test_do_notify_passes_target_as_force_route():
    with patch.object(bridge, "notify",
                      return_value=NotifyResult(True, "slack", [("slack", True, None)])) as m:
        status, result = bridge._do_notify("slack", "hi")
    assert status == "Done"
    assert m.call_args.kwargs["force_route"] == "slack"


def test_do_notify_empty_target_is_normal_fallback():
    with patch.object(bridge, "notify",
                      return_value=NotifyResult(True, "notion", [("notion", True, None)])) as m:
        bridge._do_notify("", "hi")
    assert m.call_args.kwargs["force_route"] is None


def test_do_notify_all_fail_is_error():
    with patch.object(bridge, "notify",
                      return_value=NotifyResult(False, None, [("notion", False, "down")])):
        status, result = bridge._do_notify("", "hi")
    assert status == "Error"


# ─── Queue ポーリング ─────────────────────────────────────────────────────────

def test_process_queue_processes_all_in_order():
    rows = [make_row("p1", "fire", target="K1"), make_row("p2", "notify", target="")]
    updated = []

    with patch.object(bn, "query_pending", return_value=rows), \
         patch.object(bridge, "_do_fire", return_value=("Done", "ok")) as fire, \
         patch.object(bridge, "_do_notify", return_value=("Done", "ok")) as notif, \
         patch.object(bn, "update_row", side_effect=lambda pid, **kw: updated.append(pid)):
        n = bridge.process_queue()

    assert n == 2
    assert updated == ["p1", "p2"]
    fire.assert_called_once()
    notif.assert_called_once()


def test_unknown_action_is_error():
    row = make_row("p9", "bogus")
    with patch.object(bn, "update_row") as upd:
        bridge._process_row(row)
    assert upd.call_args.kwargs["status"] == "Error"


def test_update_row_failure_does_not_raise():
    row = make_row("p1", "fire", target="K")
    with patch.object(bridge, "_do_fire", return_value=("Error", "env未設定")), \
         patch.object(bn, "update_row", side_effect=RuntimeError("notion down")):
        bridge._process_row(row)  # 例外が外に漏れなければ合格


# ─── SELFTEST ─────────────────────────────────────────────────────────────────

def test_run_selftest_writes_row_and_comment(monkeypatch):
    monkeypatch.setenv("NOTIFY_ROUTES", "discord,notion")
    monkeypatch.setenv("ROUTINE_FIRE_URL_PR_SYNC", "https://api.anthropic.com/x")
    monkeypatch.setenv("ROUTINE_FIRE_TOKEN_PR_SYNC", "tok123456")

    with patch.object(bridge, "notify",
                      return_value=NotifyResult(True, "notion", [])) as notif, \
         patch.object(bridge, "_do_fire", return_value=("Done", "ok")) as fire, \
         patch.object(bn, "create_row") as create_row, \
         patch.object(bn, "create_comment") as create_comment:
        summary = bridge.run_selftest()

    # 各経路への通知 + fire キーへの POST が行われ、結果が記録される
    assert notif.call_count >= 2
    fire.assert_called()
    create_row.assert_called_once()
    create_comment.assert_called_once()
    assert "SELFTEST" not in summary or "notify[" in summary


def test_run_dispatches_selftest_when_env_set(monkeypatch):
    monkeypatch.setenv("BRIDGE_SELFTEST", "1")
    with patch.object(bridge, "run_selftest") as st, \
         patch.object(bridge, "process_queue", return_value=0):
        bridge.run()
    st.assert_called_once()


def test_run_skips_selftest_when_env_unset(monkeypatch):
    monkeypatch.delenv("BRIDGE_SELFTEST", raising=False)
    with patch.object(bridge, "run_selftest") as st, \
         patch.object(bridge, "process_queue", return_value=0):
        bridge.run()
    st.assert_not_called()
