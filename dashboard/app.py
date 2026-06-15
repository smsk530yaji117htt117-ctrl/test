# -*- coding: utf-8 -*-
"""
app.py — PersonalOS 読み取り専用ダッシュボード（MVP / FastAPI）

`GET /` でサーバ側が Notion の5つの DB を読み、モバイル幅の軽量 HTML を返す。
**read-only**（Notion へは一切書き込まない）。

セクション単位でエラーを隔離する: あるセクションの取得/解析が失敗しても、
そのセクションだけエラー表示にして、他のセクションとページ全体は生かす。

環境変数:
  NOTION_TOKEN ... Notion インテグレーションのトークン（コミット禁止 / .gitignore 済み）。
                   このインテグレーションが対象5DBに「接続」されている必要がある。

ローカル起動:
  pip install -r requirements.txt
  uvicorn app:app --reload     # → http://127.0.0.1:8000/
"""
from __future__ import annotations

import html
import os
import re
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

import notion_reader as nr

app = FastAPI(title="PersonalOS Dashboard", docs_url=None, redoc_url=None)

JST = timezone(timedelta(hours=9))
_SECRET_RE = re.compile(r"(ntn_|secret_)[A-Za-z0-9\-_]+")


def _mask(text: object) -> str:
    """エラーメッセージ等から Notion トークンらしき文字列をマスクする。"""
    return _SECRET_RE.sub(r"\1***", str(text))


def _esc(text: object) -> str:
    return html.escape(str(text if text is not None else ""))


# ════════════════════════════════════════════════════════════════════════
# セクション・レンダラ（各々 HTML 文字列を返す純粋関数）
# ════════════════════════════════════════════════════════════════════════

def render_habit(items: list[dict]) -> str:
    if not items:
        return _empty("進行中の習慣はありません")
    rows = []
    for it in items:
        badge = '<span class="badge grad">🎓卒業候補</span>' if it["graduation"] else ""
        auto = _esc(it["auto"] or "—")
        rows.append(
            f'<li class="{"hl" if it["graduation"] else ""}">'
            f'<span class="name">{_esc(it["name"]) or "（無題）"}</span>{badge}'
            f'<span class="meta">自動化度: {auto}</span></li>'
        )
    grad_n = sum(1 for it in items if it["graduation"])
    head = f'進行中 {len(items)}件・🎓卒業候補 {grad_n}件'
    return _summary(head) + f'<ul class="list">{"".join(rows)}</ul>'


def render_stock(items: list[dict]) -> str:
    if not items:
        return _empty("在庫品目がありません")
    need = [it for it in items if it["need"]]
    rows = []
    for it in items:
        mark = '<span class="badge buy">🛒補充</span>' if it["need"] else ""
        remain = it["remain"]
        remain_s = f'{remain:g}日' if isinstance(remain, (int, float)) else "—"
        thr = it["threshold"]
        thr_s = f'{thr:g}' if isinstance(thr, (int, float)) else f'既定{nr.STOCK_DEFAULT_THRESHOLD}'
        rows.append(
            f'<li class="{"hl" if it["need"] else ""}">'
            f'<span class="name">{_esc(it["name"]) or "（無題）"}</span>{mark}'
            f'<span class="meta">残り {remain_s} / 閾値 {thr_s}</span></li>'
        )
    return _summary(f'🛒補充 {len(need)}件 / 全{len(items)}品目') + f'<ul class="list">{"".join(rows)}</ul>'


def render_chore(items: list[dict]) -> str:
    if not items:
        return _empty("定期家事がありません")
    soon = [it for it in items if it["soon"]]
    rows = []
    for it in items:
        mark = '<span class="badge soon">🧹今日明日</span>' if it["soon"] else ""
        weather = '<span class="badge weather">☀️天気依存</span>' if it["weather"] else ""
        due = it["due"]
        due_s = f'あと{due:g}日' if isinstance(due, (int, float)) else "—"
        rows.append(
            f'<li class="{"hl" if it["soon"] else ""}">'
            f'<span class="name">{_esc(it["name"]) or "（無題）"}</span>{mark}{weather}'
            f'<span class="meta">次回まで: {due_s}</span></li>'
        )
    return _summary(f'🧹今日明日 {len(soon)}件 / 全{len(items)}件') + f'<ul class="list">{"".join(rows)}</ul>'


def render_meal(items: list[dict]) -> str:
    if not items:
        return _empty("料理プールが空です")
    rows = []
    for it in items:
        days = it["days"]
        days_s = f'{days:g}日前' if isinstance(days, (int, float)) else "未提供"
        sub = " / ".join(x for x in [it["kind"], it["protein"] and f'P:{it["protein"]}'] if x)
        rows.append(
            f'<li><span class="name">🍳 {_esc(it["name"]) or "（無題）"}</span>'
            f'<span class="meta">{_esc(days_s)}{("・" + _esc(sub)) if sub else ""}</span></li>'
        )
    return _summary(f'献立候補 上位{len(items)}件（前回から日数 降順）') + f'<ul class="list">{"".join(rows)}</ul>'


def render_handoff(summary: dict) -> str:
    items = summary["items"]
    head = f'Draft {summary["count"]}件'
    if not items:
        return _summary(head) + _empty("Draft の Handoff はありません")
    rows = []
    for it in items:
        pri = _esc(it["priority"] or "—")
        to_ai = _esc(it["to_ai"] or "—")
        upd = _esc((it["updated"] or "")[:10] or "—")
        rows.append(
            f'<li><span class="name">{_esc(it["task"]) or "（無題）"}</span>'
            f'<span class="meta">優先度: {pri} / To: {to_ai} / 更新: {upd}</span></li>'
        )
    return _summary(head + f'（上位{len(items)}件）') + f'<ul class="list">{"".join(rows)}</ul>'


# ── 小物 ─────────────────────────────────────────────────────────────────

def _summary(text: str) -> str:
    return f'<p class="summary">{_esc(text)}</p>'


def _empty(text: str) -> str:
    return f'<p class="empty">{_esc(text)}</p>'


def _section(emoji_title: str, inner: str) -> str:
    return f'<section class="card"><h2>{_esc(emoji_title)}</h2>{inner}</section>'


def _safe_section(emoji_title: str, build) -> str:
    """build() を実行して HTML を返す。失敗してもそのセクションだけエラー表示にする。"""
    try:
        return _section(emoji_title, build())
    except Exception as e:  # noqa: BLE001 — セクション単位でエラーを隔離
        msg = _esc(_mask(f"{type(e).__name__}: {e}"))
        return _section(
            emoji_title,
            f'<p class="error">⚠️ このセクションの読み込みに失敗しました（他は表示されています）<br>'
            f'<code>{msg}</code></p>',
        )


# ════════════════════════════════════════════════════════════════════════
# ページ
# ════════════════════════════════════════════════════════════════════════

_CSS = """
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Hiragino Kaku Gothic ProN","Noto Sans JP",sans-serif;
background:#f5f6f8;color:#1c1e21;line-height:1.5}
.wrap{max-width:480px;margin:0 auto;padding:12px 12px 40px}
header h1{font-size:18px;margin:8px 4px 2px}
header .asof{font-size:12px;color:#65676b;margin:0 4px 12px}
.card{background:#fff;border-radius:12px;padding:12px 14px;margin:0 0 12px;
box-shadow:0 1px 3px rgba(0,0,0,.08)}
.card h2{font-size:15px;margin:0 0 8px}
.summary{font-size:13px;color:#65676b;margin:0 0 8px;font-weight:600}
.empty{font-size:13px;color:#90949c;margin:6px 0}
.error{font-size:13px;color:#b00020;margin:4px 0}
.error code{font-size:11px;word-break:break-all;color:#90949c}
ul.list{list-style:none;margin:0;padding:0}
ul.list li{padding:7px 0;border-top:1px solid #eceef1;display:flex;flex-wrap:wrap;align-items:center;gap:6px}
ul.list li:first-child{border-top:none}
ul.list li.hl{background:#fff8e1;border-radius:8px;padding-left:8px;padding-right:8px}
.name{font-size:14px;font-weight:600}
.meta{font-size:12px;color:#65676b;width:100%}
.badge{font-size:11px;padding:1px 7px;border-radius:999px;font-weight:700}
.badge.grad{background:#e3f1e6;color:#1a7f37}
.badge.buy{background:#fdecea;color:#c0392b}
.badge.soon{background:#e8f0fe;color:#1a56db}
.badge.weather{background:#fff4e0;color:#b46900}
footer{font-size:11px;color:#90949c;text-align:center;margin-top:8px}
"""


def _page(body: str) -> str:
    asof = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    return (
        "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<meta name=\"robots\" content=\"noindex\">"
        "<title>PersonalOS Dashboard</title>"
        f"<style>{_CSS}</style></head><body><div class=\"wrap\">"
        "<header><h1>📊 PersonalOS ダッシュボード</h1>"
        f"<p class=\"asof\">read-only · {asof} 時点</p></header>"
        f"{body}"
        "<footer>read-only view · 書き込みは行いません</footer>"
        "</div></body></html>"
    )


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        body = _section(
            "⚙️ セットアップが必要です",
            '<p class="error">NOTION_TOKEN が未設定です。'
            '<code>.env</code> または環境変数に設定してください（README 参照）。</p>',
        )
        return HTMLResponse(_page(body), status_code=200)

    try:
        client = nr.make_client(token)
    except Exception as e:  # noqa: BLE001
        body = _section("⚠️ 初期化エラー",
                        f'<p class="error"><code>{_esc(_mask(e))}</code></p>')
        return HTMLResponse(_page(body), status_code=200)

    sections = [
        _safe_section("📈 習慣トラッカー", lambda: render_habit(nr.fetch_habit(client))),
        _safe_section("🧺 生活在庫・消耗品", lambda: render_stock(nr.fetch_stock(client))),
        _safe_section("🧹 定期家事", lambda: render_chore(nr.fetch_chore(client))),
        _safe_section("🍳 料理・献立プール", lambda: render_meal(nr.fetch_meal(client))),
        _safe_section("🤝 AI Handoff（Draft）", lambda: render_handoff(nr.fetch_handoff(client))),
    ]
    return HTMLResponse(_page("\n".join(sections)))


@app.get("/healthz", response_class=HTMLResponse)
def healthz() -> HTMLResponse:
    """死活確認（Notion へはアクセスしない）。"""
    return HTMLResponse("ok")
