# -*- coding: utf-8 -*-
"""
監査 Med: query_database の has_more / next_cursor ページネーション。

旧実装は page_size=100 の単発で、100件超のキューをサイレントに取りこぼしていた
（get_pending_questions / get_running_pages が依存する hot path）。
全行取得と、next_cursor 欠落時の無限ループ防止を担保する。
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import notion_utils


def test_paginates_until_has_more_false():
    pages = [
        {"results": [{"id": "1"}, {"id": "2"}], "has_more": True, "next_cursor": "c1"},
        {"results": [{"id": "3"}], "has_more": False, "next_cursor": None},
    ]
    calls = []

    def fake_request(method, path, body=None):
        calls.append(body)
        return pages[len(calls) - 1]

    with patch.object(notion_utils, "_request", side_effect=fake_request):
        out = notion_utils.query_database("db-123", filter_body={"x": 1}, sorts=[{"y": 1}])

    assert [r["id"] for r in out] == ["1", "2", "3"]
    assert len(calls) == 2
    # 1回目は start_cursor なし、2回目は前回の next_cursor を渡す
    assert calls[0].get("start_cursor") is None
    assert calls[1].get("start_cursor") == "c1"
    # filter / sorts は各リクエストに付与される
    assert calls[0]["filter"] == {"x": 1}
    assert calls[1]["sorts"] == [{"y": 1}]


def test_single_page_no_cursor():
    with patch.object(notion_utils, "_request",
                      return_value={"results": [{"id": "a"}], "has_more": False}):
        out = notion_utils.query_database("db")
    assert [r["id"] for r in out] == ["a"]


def test_stops_when_next_cursor_missing_despite_has_more():
    # has_more=True でも next_cursor が無ければ停止（無限ループ防止）
    with patch.object(notion_utils, "_request",
                      return_value={"results": [{"id": "a"}], "has_more": True, "next_cursor": None}):
        out = notion_utils.query_database("db")
    assert [r["id"] for r in out] == ["a"]
