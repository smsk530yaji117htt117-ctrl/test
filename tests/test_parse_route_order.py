# -*- coding: utf-8 -*-
"""
_parse_route の順序バイアス是正の回帰テスト（requirement 3）

旧実装は VALID_ROUTES のタプル宣言順で「最初に部分一致したルート」を返していたため、
Next Route に複数候補が混在すると、宣言順という偶発的なバイアスに判定が引きずられた。
新実装は判定を決定的な優先順位（_ROUTE_PRIORITY, 安全側を上位）に固定し、入力トークン
の出現順にも VALID_ROUTES の宣言順にも依存しないことを検証する。
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from meeting_result_processor import (
    ROUTER_RULES,
    VALID_ROUTES,
    _ROUTE_PRIORITY,
    _parse_route,
    parse_synthesis,
)


def _synthesis_with_route(primary, nr):
    return (
        "### 結論\n結論\n"
        f"### タイプ判定\nprimary: {primary}\nsecondary: なし\n"
        "### 推奨成果物\n成果物\n"
        "### Human Review Required\nfalse\n"
        f"### Next Route\n{nr}\n"
    )


# ── 単一トークンは尊重する ────────────────────────────────────────────────────

@pytest.mark.parametrize("route", VALID_ROUTES)
def test_single_token_is_honored(route):
    # primary_type は無関係（型導出に頼らず明示ルートを採用）
    assert _parse_route(route, "decision") == route


# ── 複数トークンは決定的な優先順位で解決（入力順に依存しない）──────────────────

def test_multiple_tokens_resolved_by_priority_not_input_order():
    # {create_handoff, research_more} → 優先順位では research_more が上位
    assert _parse_route("create_handoff research_more", "dev_task") == "research_more"
    # 入力順を逆にしても同じ結果（入力順非依存）
    assert _parse_route("research_more create_handoff", "dev_task") == "research_more"


def test_menu_echo_all_routes_falls_to_safest():
    # LLM が選択肢メニューを丸写し → 全ルート出現。安全側 no_action が最優先。
    menu = "create_handoff | create_doc | no_action | research_more"
    assert _parse_route(menu, "dev_task") == "no_action"
    # 並べ替えても結果は不変
    reordered = "research_more / no_action / create_doc / create_handoff"
    assert _parse_route(reordered, "dev_task") == "no_action"


def test_input_order_independence_for_all_permutations():
    # どんな出現順でも、同じトークン集合なら必ず同じルートに収束する
    tokens = ["create_handoff", "create_doc", "research_more"]
    results = {
        _parse_route(" ".join(perm), "dev_task")
        for perm in itertools.permutations(tokens)
    }
    assert len(results) == 1  # 並び順が違っても判定は1つに定まる
    # 優先順位では create_doc が create_handoff / research_more より上位
    assert results == {"create_doc"}


def test_priority_is_explicit_not_valid_routes_declaration_order():
    # 旧実装は VALID_ROUTES 先頭（create_handoff）を返していた。新実装は明示優先順位に従う。
    both = "create_handoff create_doc"
    assert VALID_ROUTES[0] == "create_handoff"  # 宣言順の先頭
    assert _parse_route(both, "dev_task") == "create_doc"  # ≠ 宣言順先頭
    assert _ROUTE_PRIORITY.index("create_doc") < _ROUTE_PRIORITY.index("create_handoff")


# ── トークンが無ければ型→ルートの正準マッピングで導出 ────────────────────────

def test_no_token_falls_back_to_type_mapping():
    assert _parse_route("???", "research") == "research_more"
    assert _parse_route("", "dev_task") == "create_handoff"
    assert _parse_route("意味のない文章", "doc_task") == "create_doc"


def test_unknown_type_with_no_token_is_no_action():
    assert _parse_route("", "unknown") == "no_action"


# ── parse_synthesis 経由でも決定的（エンドツーエンド）──────────────────────────

def test_parse_synthesis_multiple_routes_is_deterministic():
    a = parse_synthesis(_synthesis_with_route("dev_task", "create_handoff research_more"))
    b = parse_synthesis(_synthesis_with_route("dev_task", "research_more create_handoff"))
    assert a.next_route == b.next_route == "research_more"
