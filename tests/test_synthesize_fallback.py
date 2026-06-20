# -*- coding: utf-8 -*-
"""
監査 Top3-③: synthesize() の OpenAI フォールバック経路のテスト。

claude_success=False（Claude ダウン）かつ openai_success=True のとき、
synthesize() は OpenAI で Synthesis を生成する。このフォールバックは
「Claude が落ちている＝最も必要な瞬間」に発火し、Notion に書かれる
ユーザー向け Synthesis を生成するが、従来テストが無かった。

注: 非同期テストプラグイン（pytest-asyncio 等）への依存を避けるため、
コルーチンは asyncio.run() で直接駆動する（既存 test_consensus.py と同方針）。
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from consensus import synthesize


def test_synthesize_uses_openai_when_claude_down():
    """Claude 失敗時、OpenAI 経路で (str, str) を返す"""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="### 結論\nフォールバックOK [確定]"))]

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-proj-test-key"}):
        with patch("openai.AsyncOpenAI", return_value=mock_client):
            result = asyncio.run(synthesize(
                question="テスト質問",
                claude_r="Claude unavailable: API_ERROR_CLAUDE",
                gemini_r="Gemini回答",
                gpt_r="GPT回答",
                claude_success=False,
                gemini_success=True,
                openai_success=True,
            ))

    assert isinstance(result, tuple)
    assert len(result) == 2
    text, tag = result
    assert isinstance(text, str)
    assert isinstance(tag, str)
    # OpenAI のレスポンス本文がそのまま使われている
    assert "フォールバックOK" in text
    # タグ抽出も機能している
    assert tag == "確定"
    # Claude ではなく OpenAI が呼ばれた
    mock_client.chat.completions.create.assert_awaited_once()


def test_synthesize_openai_handles_empty_content():
    """OpenAI が content=None を返しても空文字に正規化して落ちない"""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content=None))]

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-proj-test-key"}):
        with patch("openai.AsyncOpenAI", return_value=mock_client):
            text, tag = asyncio.run(synthesize(
                question="Q",
                claude_r="err",
                gemini_r="g",
                gpt_r="o",
                claude_success=False,
                openai_success=True,
            ))

    assert text == ""
    assert tag == "未確認"
