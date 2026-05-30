# -*- coding: utf-8 -*-
"""
PR-B: Tags 書き込み deprecate のテスト

テスト範囲:
- SYNTHESIS_PROMPT_TEMPLATE が8セクション見出しを含む (PR-A 継承)
- synthesize() が str を返す (タプルではない)
- write_back_to_notion() のシグネチャから tag が削除されている
- write_back_to_notion() の update payload に Tags フィールドが含まれない
"""
import inspect
import pytest
from unittest.mock import AsyncMock, patch, MagicMock, call

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
async def test_synthesize_returns_str():
    """synthesize() が str を返す (タプルではない)"""
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

    assert isinstance(result, str), f"synthesize() は str を返すべきですが {type(result)} が返されました"
    assert not isinstance(result, tuple), "synthesize() はタプルを返してはいけません"


# ── write_back_to_notion() シグネチャ確認 ─────────────────────────────────────

def test_write_back_to_notion_signature_no_tag():
    """write_back_to_notion() のシグネチャから tag が削除されている"""
    sig = inspect.signature(write_back_to_notion)
    params = list(sig.parameters.keys())
    expected = ["page_id", "claude_r", "gemini_r", "gpt_r", "synthesis"]
    assert params == expected, (
        f"write_back_to_notion() のパラメータが期待と異なります: {params}"
    )
    assert "tag" not in params, "write_back_to_notion() から tag パラメータが削除されていません"


# ── write_back_to_notion() の update payload に Tags が含まれないことを確認 ───

def test_write_back_to_notion_no_tags_in_payload():
    """write_back_to_notion() の update_page_properties 呼び出しに Tags が含まれない"""
    with patch("consensus.get_page") as mock_get_page, \
         patch("consensus.update_page_properties") as mock_update:
        mock_get_page.return_value = {
            "properties": {
                "Depth": {"select": None}
            }
        }

        write_back_to_notion(
            page_id="test-page-id",
            claude_r="Claude回答",
            gemini_r="Gemini回答",
            gpt_r="GPT回答",
            synthesis="統合分析テキスト",
        )

        assert mock_update.called, "update_page_properties が呼ばれていません"
        called_properties = mock_update.call_args[0][1]
        assert "Tags" not in called_properties, (
            f"Tags フィールドが update payload に含まれています: {list(called_properties.keys())}"
        )
