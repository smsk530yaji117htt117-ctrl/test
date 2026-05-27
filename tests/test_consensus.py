# -*- coding: utf-8 -*-
"""
PR-A: SYNTHESIS_PROMPT_TEMPLATE 8セクション化のテスト

テスト範囲:
- SYNTHESIS_PROMPT_TEMPLATE が8セクション見出しを含む
- synthesize() がタプル (str, str) を返す (モック使用)
- write_back_to_notion() のシグネチャが変更されていないことを確認
"""
import inspect
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from consensus import SYNTHESIS_PROMPT_TEMPLATE, synthesize, write_back_to_notion


# ── SYNTHESIS_PROMPT_TEMPLATE のテスト ────────────────────────────────────────

EXPECTED_SECTIONS = [
    "### 結論",
    "### 根拠",
    "### リスク",
    "### 推奨アクション",
    "### タイプ判定",
    "### 推奨成果物",
    "### Human Review Required",
    "### Next Route",
]


def test_synthesis_prompt_template_exists():
    """SYNTHESIS_PROMPT_TEMPLATE 定数が存在する"""
    assert isinstance(SYNTHESIS_PROMPT_TEMPLATE, str)
    assert len(SYNTHESIS_PROMPT_TEMPLATE) > 0


@pytest.mark.parametrize("section", EXPECTED_SECTIONS)
def test_synthesis_prompt_template_has_8_sections(section):
    """SYNTHESIS_PROMPT_TEMPLATE が8セクション見出しをすべて含む"""
    assert section in SYNTHESIS_PROMPT_TEMPLATE, (
        f"セクション '{section}' が SYNTHESIS_PROMPT_TEMPLATE に見つかりません"
    )


def test_synthesis_prompt_template_has_placeholders():
    """SYNTHESIS_PROMPT_TEMPLATE が必要なプレースホルダーを含む"""
    for placeholder in ["{mode}", "{question}", "{claude_section}",
                        "{gemini_section}", "{openai_section}", "{unavailable_note}"]:
        assert placeholder in SYNTHESIS_PROMPT_TEMPLATE, (
            f"プレースホルダー '{placeholder}' が見つかりません"
        )


def test_synthesis_prompt_template_format():
    """SYNTHESIS_PROMPT_TEMPLATE が .format() で展開できる"""
    result = SYNTHESIS_PROMPT_TEMPLATE.format(
        mode="3社合議",
        unavailable_note="",
        question="テスト質問",
        claude_section="Claude回答",
        gemini_section="Gemini回答",
        openai_section="OpenAI回答",
    )
    assert "テスト質問" in result
    assert "### 結論" in result
    assert "### Next Route" in result


# ── synthesize() のテスト ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_synthesize_returns_tuple():
    """synthesize() が (str, str) タプルを返す"""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        text="### 結論\nテスト結論\n### 根拠\n根拠\n"
             "### リスク\nなし\n### 推奨アクション\n次のステップ\n"
             "### タイプ判定\ndiscussion\n### 推奨成果物\n議論まとめ\n"
             "### Human Review Required\nfalse\n### Next Route\n追加調査不要"
    )]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key"}):
        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            result = await synthesize(
                question="テスト",
                claude_r="Claude回答",
                gemini_r="Gemini回答",
                gpt_r="GPT回答",
            )

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], str)
    assert isinstance(result[1], str)


# ── write_back_to_notion() シグネチャ不変確認 ─────────────────────────────────

def test_write_back_to_notion_signature_unchanged():
    """write_back_to_notion() のシグネチャが PR-A では変更されていない"""
    sig = inspect.signature(write_back_to_notion)
    params = list(sig.parameters.keys())
    expected = ["page_id", "claude_r", "gemini_r", "gpt_r", "synthesis", "tag"]
    assert params == expected, (
        f"write_back_to_notion() のパラメータが変更されています: {params}"
    )
