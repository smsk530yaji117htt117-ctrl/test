# -*- coding: utf-8 -*-
"""
監査 Med: NOTION_DATABASE_ID 未設定時の fail-fast 検証。

DB_ID が空のまま cron が走ると、handle_running_timeouts / get_pending_questions が
不透明な Notion 400/404 を cron 途中で出すだけで原因が見えにくい。main() 冒頭で
明示的に EnvironmentError を投げ、起動時に止める。
"""
import asyncio
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import consensus


def test_main_raises_when_db_id_empty():
    """DB_ID が空なら handle_running_timeouts を呼ぶ前に EnvironmentError"""
    with patch.object(consensus, "DB_ID", ""), \
         patch.object(consensus, "handle_running_timeouts") as hrt, \
         patch.object(consensus, "get_pending_questions") as gpq:
        with pytest.raises(EnvironmentError):
            asyncio.run(consensus.main())
    hrt.assert_not_called()
    gpq.assert_not_called()


def test_main_proceeds_when_db_id_set_and_no_pending():
    """DB_ID があれば検証を通過し、Pending 0件なら正常終了する"""
    with patch.object(consensus, "DB_ID", "db-123"), \
         patch.object(consensus, "handle_running_timeouts") as hrt, \
         patch.object(consensus, "get_pending_questions", return_value=[]):
        asyncio.run(consensus.main())  # 例外が漏れなければ合格
    hrt.assert_called_once()
