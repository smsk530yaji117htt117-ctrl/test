# -*- coding: utf-8 -*-
"""
notion_reader.py — PersonalOS 読み取り専用ダッシュボードの Notion 読み取り層

Notion 公式 SDK（notion-client）で各 DB を `databases.query` し、
ダッシュボード表示用の素データに変換する。**書き込みは一切しない**（read-only）。

設計方針:
- プロパティ抽出（prop_*）と「ページ群 → 表示アイテム」変換（build_*_items）は
  純関数にして、ネットワークなしでユニットテストできるようにする。
- formula 列はそのまま読む（数値/文字列/真偽/日付の中身を取り出すだけ）。
- 取得（fetch_*）は薄いラッパー。例外はここでは握りつぶさず、呼び出し側
  （app.py のセクション単位 try/except）で隔離する。
"""
from __future__ import annotations

from typing import Any

try:  # notion-client は dashboard/requirements.txt で導入（テストの純関数部は不要）
    from notion_client import Client
except ImportError:  # pragma: no cover - SDK 未導入環境でも純関数テストは通す
    Client = None  # type: ignore

# Notion REST のバージョン（repo の他コードと統一）
NOTION_VERSION = "2022-06-28"

# 対象 DB（タスク指定の ID）
DB_HABIT = "4f57bc5acb47406a840587d827a3a475"   # 📈 習慣トラッカー
DB_STOCK = "53390db16f2945d8b29083f0b069629b"   # 🧺 生活在庫・消耗品
DB_CHORE = "304f28c011004183a9d0c8b4f5db73ed"   # 🧹 定期家事
DB_MEAL = "e3a221c9a3bf47c28f843471c539df66"    # 🍳 料理・献立プール
DB_HANDOFF = "f91723343d1b4fed91127cda97adbe59"  # AI Handoff DB

# 閾値・件数（MVP の既定値）
CHORE_DUE_DAYS = 2     # 次回まで日数がこれ以下なら「今日明日」
MEAL_TOP_N = 5         # 献立候補の表示件数（前回から日数 降順）
HANDOFF_TOP_N = 5      # Draft Handoff の表示件数
STOCK_DEFAULT_THRESHOLD = 3  # アラート閾値日数が未設定の品目に使う既定値


# ════════════════════════════════════════════════════════════════════════
# プロパティ抽出（純関数）
# ════════════════════════════════════════════════════════════════════════

def _props(page: dict) -> dict:
    return (page or {}).get("properties", {}) or {}


def _plain(rich: list | None) -> str:
    return "".join(r.get("plain_text", "") for r in (rich or []))


def prop_title(page: dict, name: str) -> str:
    return _plain(_props(page).get(name, {}).get("title"))


def prop_text(page: dict, name: str) -> str:
    return _plain(_props(page).get(name, {}).get("rich_text"))


def prop_select(page: dict, name: str) -> str | None:
    sel = _props(page).get(name, {}).get("select")
    return sel.get("name") if sel else None


def prop_number(page: dict, name: str) -> float | None:
    return _props(page).get(name, {}).get("number")


def prop_checkbox(page: dict, name: str) -> bool:
    return bool(_props(page).get(name, {}).get("checkbox"))


def prop_date(page: dict, name: str) -> str | None:
    d = _props(page).get(name, {}).get("date")
    return d.get("start") if d else None


def prop_formula(page: dict, name: str) -> Any:
    """formula 列をそのまま読む（number/string/boolean/date の中身を返す）。"""
    f = _props(page).get(name, {}).get("formula") or {}
    ftype = f.get("type")
    if ftype == "number":
        return f.get("number")
    if ftype == "string":
        return f.get("string")
    if ftype == "boolean":
        return f.get("boolean")
    if ftype == "date":
        d = f.get("date")
        return d.get("start") if d else None
    return None


def _num_or(value: Any, fallback: float) -> float:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else fallback


# ════════════════════════════════════════════════════════════════════════
# ページ群 → 表示アイテム（純関数）
# ════════════════════════════════════════════════════════════════════════

def is_graduation(auto: str | None) -> bool:
    """自動化度が 4（ほぼ自動）/ 5（自動）なら卒業候補。

    選択肢は "1意識的".."5自動" の形式。先頭の数字で 4/5 を判定する。
    """
    if not auto:
        return False
    return auto.strip()[:1] in {"4", "5"}


def build_habit_items(pages: list[dict]) -> list[dict]:
    """習慣トラッカー（状態=進行中で取得済み）→ 卒業候補を先頭に並べる。"""
    items = []
    for p in pages:
        auto = prop_select(p, "自動化度")
        items.append({
            "name": prop_title(p, "習慣"),
            "auto": auto,
            "graduation": is_graduation(auto),
        })
    items.sort(key=lambda x: (not x["graduation"], x["name"] or ""))
    return items


def build_stock_items(pages: list[dict]) -> list[dict]:
    """生活在庫 → 推定残り日数 ≤ アラート閾値日数 を補充対象としてマーク。"""
    items = []
    for p in pages:
        remain = prop_formula(p, "推定残り日数")
        threshold = prop_number(p, "アラート閾値日数")
        thr = threshold if isinstance(threshold, (int, float)) else STOCK_DEFAULT_THRESHOLD
        need = isinstance(remain, (int, float)) and remain <= thr
        items.append({
            "name": prop_title(p, "品目"),
            "remain": remain,
            "threshold": threshold,
            "need": bool(need),
        })
    # 補充対象を先頭に、残り日数が少ない順
    items.sort(key=lambda x: (not x["need"], _num_or(x["remain"], float("inf"))))
    return items


def build_chore_items(pages: list[dict]) -> list[dict]:
    """定期家事 → 次回まで日数 ≤ 2 を「今日明日」、天気依存はマーク。"""
    items = []
    for p in pages:
        due = prop_formula(p, "次回まで日数")
        items.append({
            "name": prop_title(p, "家事名"),
            "due": due,
            "weather": prop_checkbox(p, "天気依存"),
            "soon": isinstance(due, (int, float)) and due <= CHORE_DUE_DAYS,
        })
    items.sort(key=lambda x: (not x["soon"], _num_or(x["due"], float("inf"))))
    return items


def build_meal_items(pages: list[dict], top_n: int = MEAL_TOP_N) -> list[dict]:
    """料理プール → 前回から日数 降順 top N を献立候補に。

    前回から日数が未取得（None）の行は末尾扱いにして、数値が明確な
    「久しく作っていない料理」を上位に出す。
    """
    items = []
    for p in pages:
        items.append({
            "name": prop_title(p, "料理名"),
            "days": prop_formula(p, "前回から日数"),
            "kind": prop_select(p, "種別"),
            "protein": prop_select(p, "タンパク質"),
        })
    items.sort(key=lambda x: _num_or(x["days"], float("-inf")), reverse=True)
    return items[:top_n]


def build_handoff_summary(pages: list[dict], top_n: int = HANDOFF_TOP_N) -> dict:
    """AI Handoff（Status=Draft で取得済み）→ 件数＋上位 N 件。"""
    items = []
    for p in pages[:top_n]:
        items.append({
            "task": prop_title(p, "Task"),
            "priority": prop_select(p, "Priority"),
            "to_ai": prop_select(p, "To AI"),
            "updated": prop_date(p, "Updated"),
        })
    return {"count": len(pages), "items": items}


# ════════════════════════════════════════════════════════════════════════
# 取得（薄いラッパー / ネットワーク）
# ════════════════════════════════════════════════════════════════════════

def make_client(token: str):
    """Notion 公式クライアントを作る（読み取り専用に使う）。"""
    if Client is None:
        raise RuntimeError("notion-client が未インストールです（requirements.txt を導入してください）")
    return Client(auth=token, notion_version=NOTION_VERSION)


def query_all(
    client,
    database_id: str,
    *,
    filter: dict | None = None,
    sorts: list | None = None,
    max_pages: int = 10,
) -> list[dict]:
    """databases.query をページネーションして全件取得する（read-only）。"""
    results: list[dict] = []
    cursor: str | None = None
    for _ in range(max_pages):
        kwargs: dict[str, Any] = {"database_id": database_id, "page_size": 100}
        if filter:
            kwargs["filter"] = filter
        if sorts:
            kwargs["sorts"] = sorts
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.databases.query(**kwargs)
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return results


def fetch_habit(client) -> list[dict]:
    pages = query_all(client, DB_HABIT,
                      filter={"property": "状態", "select": {"equals": "進行中"}})
    return build_habit_items(pages)


def fetch_stock(client) -> list[dict]:
    return build_stock_items(query_all(client, DB_STOCK))


def fetch_chore(client) -> list[dict]:
    return build_chore_items(query_all(client, DB_CHORE))


def fetch_meal(client) -> list[dict]:
    return build_meal_items(query_all(client, DB_MEAL))


def fetch_handoff(client) -> dict:
    pages = query_all(client, DB_HANDOFF,
                      filter={"property": "Status", "select": {"equals": "Draft"}},
                      sorts=[{"property": "Updated", "direction": "descending"}])
    return build_handoff_summary(pages)
