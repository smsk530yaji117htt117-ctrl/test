# -*- coding: utf-8 -*-
"""
監査 Top3-③: process_one() の中核パイプラインのテスト。

process_one() は毎 cron ティックで本番 Notion 書き込みを行うが、
MULTI_API_FAILURE early-exit / NOTION_WRITE_ERROR 再 raise / 楽観ロック skip
がいずれも未テストだった。回帰すると全本番行を破壊しうる。

注: コルーチンは asyncio.run() で直接駆動（既存テストと同方針、追加依存なし）。
"""
import asyncio
import os
import sys
from unittest.mock import patch, AsyncMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import consensus


def _page():
    return {"id": "p1", "properties": {"Question": {"title": [{"plain_text": "テスト質問"}]}}}


def _results(claude=True, gemini=True, openai=True):
    return {
        "claude": {"text": "c", "ok": claude},
        "gemini": {"text": "g", "ok": gemini},
        "openai": {"text": "o", "ok": openai},
    }


def test_happy_path_writes_back_and_routes():
    """3社成功: write_back と routing が1回ずつ呼ばれ、record_error は呼ばれない"""
    with patch.object(consensus, "try_claim_page", return_value=True), \
         patch.object(consensus, "ask_all_ai", AsyncMock(return_value=_results())), \
         patch.object(consensus, "synthesize", AsyncMock(return_value=("synth", "確定"))), \
         patch.object(consensus, "write_back_to_notion") as wb, \
         patch.object(consensus, "record_error") as rec, \
         patch.object(consensus, "route_synthesis_result") as route:
        asyncio.run(consensus.process_one(_page()))

    wb.assert_called_once()
    route.assert_called_once()
    rec.assert_not_called()


def test_two_ai_failure_records_multi_failure_and_skips_write():
    """2社失敗: MULTI_API_FAILURE を記録し、synthesize / write_back を呼ばない"""
    with patch.object(consensus, "try_claim_page", return_value=True), \
         patch.object(consensus, "ask_all_ai",
                      AsyncMock(return_value=_results(gemini=False, openai=False))), \
         patch.object(consensus, "synthesize", AsyncMock()) as syn, \
         patch.object(consensus, "write_back_to_notion") as wb, \
         patch.object(consensus, "record_error") as rec, \
         patch.object(consensus, "route_synthesis_result") as route:
        asyncio.run(consensus.process_one(_page()))

    rec.assert_called_once()
    assert rec.call_args[0][1] == "MULTI_API_FAILURE"
    syn.assert_not_called()
    wb.assert_not_called()
    route.assert_not_called()


def test_write_back_error_records_and_reraises():
    """書き戻し失敗: NOTION_WRITE_ERROR を記録し、例外を再 raise（routing には進まない）"""
    with patch.object(consensus, "try_claim_page", return_value=True), \
         patch.object(consensus, "ask_all_ai", AsyncMock(return_value=_results())), \
         patch.object(consensus, "synthesize", AsyncMock(return_value=("synth", "確定"))), \
         patch.object(consensus, "write_back_to_notion",
                      side_effect=RuntimeError("notion boom")), \
         patch.object(consensus, "record_error") as rec, \
         patch.object(consensus, "route_synthesis_result") as route:
        with pytest.raises(RuntimeError):
            asyncio.run(consensus.process_one(_page()))

    rec.assert_called_once()
    assert rec.call_args[0][1] == "NOTION_WRITE_ERROR"
    route.assert_not_called()


def test_skips_when_claim_fails():
    """楽観ロック失敗: ask_all_ai に進まず即 return（二重処理を防ぐ）"""
    with patch.object(consensus, "try_claim_page", return_value=False), \
         patch.object(consensus, "ask_all_ai", AsyncMock()) as ask, \
         patch.object(consensus, "record_error") as rec:
        asyncio.run(consensus.process_one(_page()))

    ask.assert_not_called()
    rec.assert_not_called()
