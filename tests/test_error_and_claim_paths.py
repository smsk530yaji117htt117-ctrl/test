# -*- coding: utf-8 -*-
"""
監査 Med/Low（安全網）: consensus の小粒だが本番に効くユーティリティのテスト。
いずれもモックのみで実挙動は変更しない。

対象:
- classify_error: エラー種別ルーティング（壊れると全エラーが UNKNOWN 化し監視不能）
- record_error: Notion書込み失敗時の status-only 二段フォールバック
- try_claim_page: 楽観ロック（二重処理の唯一のガード）
- write_back_to_notion: Depth 上書きガード（ユーザー設定 Depth を壊さない）
"""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import consensus


# ── classify_error ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("msg,expected", [
    ("anthropic rate limit", "API_ERROR_CLAUDE"),
    ("Claude timeout", "API_ERROR_CLAUDE"),
    ("gemini quota", "API_ERROR_GEMINI"),
    ("google internal", "API_ERROR_GEMINI"),
    ("openai 500", "API_ERROR_OPENAI"),
    ("GPT overloaded", "API_ERROR_OPENAI"),
    ("Notion API エラー 409", "NOTION_WRITE_ERROR"),
    ("something else entirely", "UNKNOWN_ERROR"),
])
def test_classify_error(msg, expected):
    assert consensus.classify_error(Exception(msg)) == expected


# ── record_error の二段フォールバック ───────────────────────────────────────────
def test_record_error_falls_back_to_status_only():
    """1回目の full write が失敗したら status-only 更新を試み、例外を外に出さない"""
    calls = []

    def side_effect(page_id, props):
        calls.append(props)
        if len(calls) == 1:
            raise RuntimeError("notion write boom")  # full write 失敗
        return {}  # status-only は成功

    with patch.object(consensus, "update_page_properties", side_effect=side_effect):
        consensus.record_error("p1", "UNKNOWN_ERROR", "detail")  # 例外が漏れなければ合格

    assert len(calls) == 2
    # 2回目は Status のみ
    assert calls[1] == {"Status": {"select": {"name": "Error"}}}


def test_record_error_swallows_second_failure():
    """status-only もさらに失敗しても例外を外に出さない"""
    with patch.object(consensus, "update_page_properties", side_effect=RuntimeError("always fails")):
        consensus.record_error("p1", "UNKNOWN_ERROR", "detail")  # 例外が漏れなければ合格


# ── try_claim_page（楽観ロック）────────────────────────────────────────────────
def _page_with_status(name):
    return {"properties": {"Status": {"select": {"name": name}}}}


def test_try_claim_page_true_when_running_after_refresh():
    with patch.object(consensus, "update_page_properties"), \
         patch.object(consensus, "get_page", return_value=_page_with_status("Running")):
        assert consensus.try_claim_page("p1") is True


def test_try_claim_page_false_when_other_worker_took_it():
    with patch.object(consensus, "update_page_properties"), \
         patch.object(consensus, "get_page", return_value=_page_with_status("Pending")):
        assert consensus.try_claim_page("p1") is False


# ── write_back_to_notion の Depth 上書きガード ──────────────────────────────────
def _capture_props():
    captured = {}

    def fake_update(page_id, props):
        captured.update(props)
        return {}

    return captured, fake_update


def test_write_back_sets_depth_when_empty():
    captured, fake_update = _capture_props()
    with patch.object(consensus, "get_page", return_value={"properties": {"Depth": {"select": None}}}), \
         patch.object(consensus, "update_page_properties", side_effect=fake_update):
        consensus.write_back_to_notion("p1", "c", "g", "o", "synth", "確定")
    assert captured.get("Depth") == {"select": {"name": "Consensus"}}


def test_write_back_preserves_existing_depth():
    captured, fake_update = _capture_props()
    with patch.object(consensus, "get_page",
                      return_value={"properties": {"Depth": {"select": {"name": "Deep"}}}}), \
         patch.object(consensus, "update_page_properties", side_effect=fake_update):
        consensus.write_back_to_notion("p1", "c", "g", "o", "synth", "確定")
    assert "Depth" not in captured  # 既設定は上書きしない
