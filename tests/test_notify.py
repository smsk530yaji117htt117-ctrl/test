# -*- coding: utf-8 -*-
"""notify.py のテスト（全経路 mock）。

検証範囲: フォールバック順序 / notion終端保証 / 例外封じ / dedupe / force_route /
          level=error メンション / 401-403 の Queue 行フォールバック / シークレットマスク
"""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import bridge_notion as bn
import notify
from notify import notify as do_notify, NotifyResult, mask_secrets


@pytest.fixture(autouse=True)
def clean_routes(monkeypatch):
    for var in ["NOTIFY_ROUTES", "DISCORD_WEBHOOK_URL", "SLACK_WEBHOOK_URL",
                "EMAIL_API_URL", "EMAIL_API_KEY", "EMAIL_TO"]:
        monkeypatch.delenv(var, raising=False)
    yield


def test_fallback_first_success_stops(monkeypatch):
    """最初に成功した経路で停止し、後続経路は試さない"""
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/abc/def")
    monkeypatch.setenv("NOTIFY_ROUTES", "discord,slack,notion")
    calls = []

    def fake_post(url, headers, payload, timeout=30):
        calls.append(url)
        return 204, {}

    with patch.object(bn, "http_post_json", side_effect=fake_post), \
         patch.object(bn, "create_comment") as comment:
        res = do_notify("hello", source="t")

    assert res.ok and res.route == "discord"
    assert len(calls) == 1
    comment.assert_not_called()


def test_fallback_to_notion_when_others_unconfigured(monkeypatch):
    """discord/slack の env 未設定 → スキップして notion 終端で配送"""
    monkeypatch.setenv("NOTIFY_ROUTES", "discord,slack,notion")
    with patch.object(bn, "create_comment") as comment:
        res = do_notify("hello", source="t")

    assert res.ok and res.route == "notion"
    comment.assert_called_once()
    skipped = {r: err for r, ok, err in res.attempts}
    assert "env未設定" in skipped["discord"]


def test_discord_failure_falls_through_to_notion(monkeypatch):
    """discord が HTTP 失敗 → notion 終端へフォールバック"""
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
    monkeypatch.setenv("NOTIFY_ROUTES", "discord,notion")
    with patch.object(bn, "http_post_json", return_value=(500, "err")), \
         patch.object(bn, "create_comment") as comment:
        res = do_notify("hi", source="t")

    assert res.ok and res.route == "notion"
    comment.assert_called_once()


def test_notion_always_appended_as_terminal(monkeypatch):
    """NOTIFY_ROUTES に notion が無くても終端として付与される"""
    monkeypatch.setenv("NOTIFY_ROUTES", "discord")
    with patch.object(bn, "create_comment") as comment:
        res = do_notify("hi", source="t")
    assert res.ok and res.route == "notion"
    comment.assert_called_once()


def test_exception_is_suppressed(monkeypatch):
    """経路送信で例外 → notify は投げず、attempts に記録して次へ"""
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
    monkeypatch.setenv("NOTIFY_ROUTES", "discord,notion")
    with patch.object(bn, "http_post_json", side_effect=RuntimeError("boom")), \
         patch.object(bn, "create_comment"):
        res = do_notify("hi", source="t")
    assert res.ok and res.route == "notion"
    assert any(r == "discord" and not ok for r, ok, err in res.attempts)


def test_total_failure_does_not_raise(monkeypatch):
    """全経路失敗でも例外を投げず ok=False を返す"""
    monkeypatch.setenv("NOTIFY_ROUTES", "notion")
    with patch.object(bn, "create_comment", side_effect=RuntimeError("down")):
        res = do_notify("hi", source="t")
    assert res.ok is False and res.route is None


def test_force_route_restricts_candidates(monkeypatch):
    """force_route 指定時はその経路のみ（+ notion 終端）"""
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/x/y")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/x/y/z")
    seen = []

    def fake_post(url, headers, payload, timeout=30):
        seen.append(url)
        return 200, {}

    with patch.object(bn, "http_post_json", side_effect=fake_post), \
         patch.object(bn, "create_comment"):
        res = do_notify("hi", source="t", force_route="slack")

    assert res.ok and res.route == "slack"
    assert all("slack" in u for u in seen)
    assert not any(r == "discord" for r, _, _ in res.attempts)


def test_dedupe_skips_recent(monkeypatch):
    """直近30分の Done 行 Result に同一 dedupe_key → 送信しない"""
    row = {"properties": {"Result": {"type": "rich_text",
                                      "rich_text": [{"plain_text": "dedupe_key=k1 route=notion"}]}}}
    with patch.object(bn, "query_recent_done", return_value=[row]), \
         patch.object(bn, "create_comment") as comment:
        res = do_notify("hi", source="t", dedupe_key="k1")
    assert res.ok and res.route == "dedupe"
    comment.assert_not_called()


def test_dedupe_records_marker_on_success(monkeypatch):
    """dedupe_key 指定の送信成功時に marker 付き Done 行を Queue へ残す"""
    monkeypatch.setenv("NOTIFY_ROUTES", "notion")
    with patch.object(bn, "query_recent_done", return_value=[]), \
         patch.object(bn, "create_comment"), \
         patch.object(bn, "create_row") as create_row:
        res = do_notify("hi", source="t", dedupe_key="k2")
    assert res.ok
    args, kwargs = create_row.call_args
    assert "dedupe_key=k2" in kwargs["result"]


def test_error_level_includes_mention(monkeypatch):
    """level=error 時は notion コメントに指定ユーザーのメンションを含める"""
    monkeypatch.setenv("NOTIFY_ROUTES", "notion")
    with patch.object(bn, "create_comment") as comment:
        do_notify("alert", source="t", level="error")
    page_id, rich = comment.call_args[0]
    assert any(p.get("type") == "mention"
               and p["mention"]["user"]["id"] == bn.ERROR_MENTION_USER_ID
               for p in rich)


def test_notion_permission_error_writes_queue_row(monkeypatch):
    """notion コメントが 403 → Bridge Queue 行を終端として ok=True"""
    monkeypatch.setenv("NOTIFY_ROUTES", "notion")
    with patch.object(bn, "create_comment", side_effect=bn.HttpError(403, "no access")), \
         patch.object(bn, "create_row") as create_row:
        res = do_notify("hi", source="t")
    assert res.ok and res.route == "notion"
    create_row.assert_called_once()


def test_mask_secrets_patterns_and_env(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/123/secrettoken")
    text = ("token sk-ant-abc123 and ntn_deadbeef and Bearer xyz.123 "
            "and https://discord.com/api/webhooks/123/secrettoken")
    masked = mask_secrets(text)
    assert "sk-ant-abc123" not in masked
    assert "ntn_deadbeef" not in masked
    assert "secrettoken" not in masked
    assert "Bearer xyz.123" not in masked
