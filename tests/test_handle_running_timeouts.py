# -*- coding: utf-8 -*-
"""
監査 Top3-②関連: handle_running_timeouts() のテスト。

RUNNING_TIMEOUT_MINUTES を短縮（60→15分・env 上書き可）した変更に合わせ、
「閾値超過 → Error 昇格 / 未超過 → 据え置き / Running 無し → no-op /
timestamp 欠落 → スキップ」を担保する。閾値は env 値に追従して計算する。
"""
import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import consensus


def _running_page(page_id: str, minutes_ago: float) -> dict:
    t = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return {"id": page_id, "last_edited_time": t.isoformat().replace("+00:00", "Z")}


def test_no_running_pages_is_noop():
    with patch.object(consensus, "get_running_pages", return_value=[]), \
         patch.object(consensus, "update_page_properties") as up:
        consensus.handle_running_timeouts()
    up.assert_not_called()


def test_stale_running_promoted_to_error():
    over = consensus.RUNNING_TIMEOUT_MINUTES + 5
    with patch.object(consensus, "get_running_pages",
                      return_value=[_running_page("p1", over)]), \
         patch.object(consensus, "update_page_properties") as up:
        consensus.handle_running_timeouts()

    up.assert_called_once()
    props = up.call_args[0][1]
    assert props["Status"]["select"]["name"] == "Error"


def test_recent_running_untouched():
    under = max(consensus.RUNNING_TIMEOUT_MINUTES - 5, 1)
    with patch.object(consensus, "get_running_pages",
                      return_value=[_running_page("p1", under)]), \
         patch.object(consensus, "update_page_properties") as up:
        consensus.handle_running_timeouts()
    up.assert_not_called()


def test_missing_timestamp_skipped():
    with patch.object(consensus, "get_running_pages",
                      return_value=[{"id": "p1", "last_edited_time": ""}]), \
         patch.object(consensus, "update_page_properties") as up:
        consensus.handle_running_timeouts()
    up.assert_not_called()
