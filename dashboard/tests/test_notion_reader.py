# -*- coding: utf-8 -*-
"""
notion_reader の純関数（プロパティ抽出 / 閾値判定 / 並び替え）のテスト。

ネットワーク・FastAPI 不要（notion-client は import 時 optional）。
リポジトリ全体の pytest から実行されても安全（fastapi を import しない）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import notion_reader as nr


# ── 疑似 Notion ページの組み立てヘルパ ────────────────────────────────────────

def _page(**props):
    return {"properties": props}


def _title(text):
    return {"type": "title", "title": [{"plain_text": text}]}


def _select(name):
    return {"type": "select", "select": ({"name": name} if name else None)}


def _number(n):
    return {"type": "number", "number": n}


def _checkbox(b):
    return {"type": "checkbox", "checkbox": b}


def _formula_number(n):
    return {"type": "formula", "formula": {"type": "number", "number": n}}


def _date(start):
    return {"type": "date", "date": ({"start": start} if start else None)}


# ── プロパティ抽出 ────────────────────────────────────────────────────────────

def test_prop_extractors_basic():
    p = _page(品目=_title("味噌"), 在庫数=_number(3), 区分=_select("不規則"),
              天気依存=_checkbox(True), 最終補充日=_date("2026-06-01"))
    assert nr.prop_title(p, "品目") == "味噌"
    assert nr.prop_number(p, "在庫数") == 3
    assert nr.prop_select(p, "区分") == "不規則"
    assert nr.prop_checkbox(p, "天気依存") is True
    assert nr.prop_date(p, "最終補充日") == "2026-06-01"


def test_prop_missing_is_safe():
    p = _page()
    assert nr.prop_title(p, "なし") == ""
    assert nr.prop_number(p, "なし") is None
    assert nr.prop_select(p, "なし") is None
    assert nr.prop_checkbox(p, "なし") is False


def test_prop_formula_reads_each_type():
    assert nr.prop_formula(_page(f=_formula_number(5)), "f") == 5
    assert nr.prop_formula(
        _page(f={"type": "formula", "formula": {"type": "string", "string": "x"}}), "f") == "x"
    assert nr.prop_formula(
        _page(f={"type": "formula", "formula": {"type": "boolean", "boolean": True}}), "f") is True
    assert nr.prop_formula(
        _page(f={"type": "formula", "formula": {"type": "date", "date": {"start": "2026-06-15"}}}),
        "f") == "2026-06-15"


# ── 1. 習慣: 卒業候補（自動化度 4/5）─────────────────────────────────────────

def test_is_graduation():
    assert nr.is_graduation("4ほぼ自動") is True
    assert nr.is_graduation("5自動") is True
    assert nr.is_graduation("3半自動") is False
    assert nr.is_graduation("1意識的") is False
    assert nr.is_graduation(None) is False


def test_build_habit_items_sorts_graduation_first():
    pages = [
        _page(習慣=_title("朝散歩"), 自動化度=_select("3半自動")),
        _page(習慣=_title("家計簿"), 自動化度=_select("5自動")),
        _page(習慣=_title("瞑想"), 自動化度=_select("4ほぼ自動")),
    ]
    items = nr.build_habit_items(pages)
    assert [i["name"] for i in items[:2]] == ["家計簿", "瞑想"]
    assert all(i["graduation"] for i in items[:2])
    assert items[2]["name"] == "朝散歩" and items[2]["graduation"] is False


# ── 2. 在庫: 推定残り日数 ≤ 閾値 → 補充 ──────────────────────────────────────

def test_build_stock_marks_low_stock_and_sorts():
    pages = [
        _page(品目=_title("十分品"), 推定残り日数=_formula_number(30), アラート閾値日数=_number(5)),
        _page(品目=_title("補充品"), 推定残り日数=_formula_number(2), アラート閾値日数=_number(5)),
        _page(品目=_title("ちょうど"), 推定残り日数=_formula_number(5), アラート閾値日数=_number(5)),
    ]
    items = nr.build_stock_items(pages)
    needs = [i["name"] for i in items if i["need"]]
    assert needs == ["補充品", "ちょうど"]  # ≤ 閾値（境界含む）、残り少ない順
    assert items[0]["name"] == "補充品"
    assert items[-1]["name"] == "十分品"


def test_build_stock_default_threshold_when_missing():
    # アラート閾値日数 未設定 → 既定値(3) で判定
    p_low = _page(品目=_title("既定で補充"), 推定残り日数=_formula_number(2))
    p_ok = _page(品目=_title("既定でOK"), 推定残り日数=_formula_number(10))
    items = nr.build_stock_items([p_low, p_ok])
    by = {i["name"]: i for i in items}
    assert by["既定で補充"]["need"] is True
    assert by["既定でOK"]["need"] is False


# ── 3. 家事: 次回まで日数 ≤ 2 → 今日明日 / 天気依存マーク ────────────────────

def test_build_chore_marks_soon_and_weather():
    pages = [
        _page(家事名=_title("換気扇"), 次回まで日数=_formula_number(10), 天気依存=_checkbox(False)),
        _page(家事名=_title("布団干し"), 次回まで日数=_formula_number(1), 天気依存=_checkbox(True)),
        _page(家事名=_title("ゴミ出し"), 次回まで日数=_formula_number(2), 天気依存=_checkbox(False)),
    ]
    items = nr.build_chore_items(pages)
    soon = [i["name"] for i in items if i["soon"]]
    assert soon == ["布団干し", "ゴミ出し"]  # ≤2、近い順
    assert next(i for i in items if i["name"] == "布団干し")["weather"] is True
    assert items[-1]["name"] == "換気扇"


# ── 4. 料理: 前回から日数 降順 top5 ─────────────────────────────────────────

def test_build_meal_items_desc_top_n():
    pages = [
        _page(料理名=_title(f"dish{d}"), 前回から日数=_formula_number(d))
        for d in [1, 9, 3, 20, 7, 15]
    ]
    items = nr.build_meal_items(pages, top_n=5)
    assert [i["days"] for i in items] == [20, 15, 9, 7, 3]
    assert len(items) == 5


def test_build_meal_none_days_sorted_last():
    pages = [
        _page(料理名=_title("未提供"), 前回から日数={"type": "formula", "formula": {"type": "number", "number": None}}),
        _page(料理名=_title("久々"), 前回から日数=_formula_number(40)),
    ]
    items = nr.build_meal_items(pages, top_n=5)
    assert items[0]["name"] == "久々"
    assert items[-1]["name"] == "未提供"


# ── 5. Handoff: Draft 件数 + 上位5件 ────────────────────────────────────────

def test_build_handoff_summary_count_and_top():
    pages = [
        _page(Task=_title(f"t{i}"), Status=_select("Draft"), Priority=_select("High"),
              **{"To AI": _select("Claude Code"), "Updated": _date(f"2026-06-{10 + i:02d}")})
        for i in range(7)
    ]
    summary = nr.build_handoff_summary(pages, top_n=5)
    assert summary["count"] == 7          # 件数は全件
    assert len(summary["items"]) == 5     # 表示は上位5件
    assert summary["items"][0]["task"] == "t0"
    assert summary["items"][0]["to_ai"] == "Claude Code"
