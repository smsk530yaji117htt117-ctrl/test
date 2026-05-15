"""Tech Pulse API.

Read-only HTTP API serving the latest snapshot produced by collector/.
Designed to be deployed on Vercel (Python serverless) and listed on
RapidAPI for monetization. RapidAPI handles auth and billing; this
service trusts its X-RapidAPI-Proxy-Secret header in production.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from collections import Counter
from io import StringIO
import csv

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "daily"
LATEST = ROOT / "data" / "latest.json"

RAPIDAPI_SECRET = os.environ.get("RAPIDAPI_PROXY_SECRET")

app = FastAPI(
    title="Tech Pulse API",
    description="Daily aggregated tech trends from Hacker News, GitHub, and Reddit.",
    version="1.0.0",
)


def _check_auth(secret: str | None) -> None:
    if RAPIDAPI_SECRET and secret != RAPIDAPI_SECRET:
        raise HTTPException(status_code=401, detail="unauthorized")


def _load_latest() -> dict:
    if not LATEST.exists():
        raise HTTPException(status_code=503, detail="snapshot not yet generated")
    return json.loads(LATEST.read_text())


def _load_date(date: str) -> dict:
    path = DATA_DIR / f"{date}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"no snapshot for {date}")
    return json.loads(path.read_text())


LANDING_HTML = (ROOT / "api" / "landing.html")


@app.get("/", response_class=HTMLResponse)
def landing() -> HTMLResponse:
    if LANDING_HTML.exists():
        return HTMLResponse(LANDING_HTML.read_text())
    return HTMLResponse("<h1>Tech Pulse API</h1><p>See /docs</p>")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat()}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    from datetime import timezone as _tz
    try:
        data = _load_latest()
    except HTTPException:
        return HTMLResponse(
            "<h1>Tech Pulse — Dashboard</h1><p>No snapshot yet. The collector has not run.</p>",
            status_code=200,
        )

    src = data.get("sources", {})
    rows = []
    for name, items in src.items():
        if isinstance(items, list):
            rows.append((name, len(items)))
        elif isinstance(items, dict):  # reddit
            for sub, posts in items.items():
                rows.append((f"reddit/{sub}", len(posts)))

    enriched = 0
    total = 0
    for items in src.values():
        if isinstance(items, list):
            total += len(items)
            enriched += sum(1 for it in items if isinstance(it, dict) and it.get("summary_ja"))

    kws_overall = (data.get("trending_keywords") or [])[:10]
    kws_ja = (data.get("trending_keywords_ja") or [])[:10]
    kws_en = (data.get("trending_keywords_en") or [])[:10]

    history_files = sorted(DATA_DIR.glob("*.json"), reverse=True)[:7]
    history = [{"date": p.stem, "size": p.stat().st_size} for p in history_files]

    age_seconds = None
    try:
        gen = datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))
        age_seconds = int((datetime.now(_tz.utc) - gen).total_seconds())
    except Exception:
        pass

    return HTMLResponse(_render_dashboard(
        data["generated_at"], age_seconds, rows, enriched, total,
        kws_overall, kws_ja, kws_en, history,
    ))


def _render_dashboard(generated_at, age_seconds, rows, enriched, total,
                      kws_overall, kws_ja, kws_en, history) -> str:
    def kw_list(kws):
        if not kws:
            return "<em>(no data)</em>"
        return "".join(
            f"<li><code>{k['keyword']}</code> <span class='c'>×{k['count']}</span></li>"
            for k in kws
        )
    src_rows = "".join(
        f"<tr><td><code>{n}</code></td><td>{c}</td></tr>" for n, c in rows
    ) or "<tr><td colspan=2><em>no sources</em></td></tr>"
    hist_rows = "".join(
        f"<tr><td>{h['date']}</td><td>{h['size']:,} bytes</td></tr>" for h in history
    )
    fresh_class = "ok" if (age_seconds is not None and age_seconds < 30 * 3600) else "warn"
    age_text = f"{age_seconds // 3600}h {age_seconds % 3600 // 60}m ago" if age_seconds else "?"
    summary_pct = f"{(enriched / total * 100):.0f}%" if total else "0%"
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Tech Pulse — Dashboard</title>
<style>
:root {{ color-scheme: light dark; --fg:#111; --muted:#666; --bg:#fff; --card:#f5f6f8; --ok:#0a7c2f; --warn:#b35900; }}
@media (prefers-color-scheme: dark){{ :root {{ --fg:#eee; --muted:#aaa; --bg:#0b0d10; --card:#15181d; }} }}
body {{ font:14px/1.5 system-ui,-apple-system,sans-serif; color:var(--fg); background:var(--bg); margin:0; padding:24px; max-width:980px; margin:0 auto; }}
h1 {{ margin:0 0 16px; }}
h2 {{ margin:24px 0 12px; font-size:1.05rem; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; }}
.card {{ background:var(--card); padding:16px 18px; border-radius:8px; }}
.kpi {{ font-size:1.7rem; font-weight:600; }}
.kpi-label {{ color:var(--muted); font-size:.85rem; }}
.ok {{ color:var(--ok); }}
.warn {{ color:var(--warn); }}
table {{ width:100%; border-collapse:collapse; font-size:.9rem; }}
th, td {{ text-align:left; padding:6px 10px; border-bottom:1px solid #80808033; }}
ul {{ margin:0; padding-left:18px; }}
li {{ margin:3px 0; }}
.c {{ color:var(--muted); font-size:.85rem; }}
code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.9em; }}
footer {{ margin-top:32px; color:var(--muted); font-size:.85rem; }}
</style></head><body>
<h1>Tech Pulse — Dashboard</h1>
<div class="grid">
  <div class="card">
    <div class="kpi {fresh_class}">{age_text}</div>
    <div class="kpi-label">since last snapshot</div>
    <div style="margin-top:6px"><code>{generated_at}</code></div>
  </div>
  <div class="card">
    <div class="kpi">{total}</div>
    <div class="kpi-label">total items collected</div>
  </div>
  <div class="card">
    <div class="kpi">{summary_pct}</div>
    <div class="kpi-label">AI-summarized ({enriched}/{total})</div>
  </div>
</div>

<h2>Sources</h2>
<div class="card"><table><tr><th>source</th><th>items</th></tr>{src_rows}</table></div>

<h2>Trending — Overall</h2>
<div class="card"><ul>{kw_list(kws_overall)}</ul></div>

<div class="grid">
  <div><h2>Japanese</h2><div class="card"><ul>{kw_list(kws_ja)}</ul></div></div>
  <div><h2>English</h2><div class="card"><ul>{kw_list(kws_en)}</ul></div></div>
</div>

<h2>Recent snapshots</h2>
<div class="card"><table><tr><th>date</th><th>size</th></tr>{hist_rows}</table></div>

<footer>Auto-refreshes daily via GitHub Actions. <a href="/docs">/docs</a> · <a href="/v1/pulse/latest">/v1/pulse/latest</a></footer>
</body></html>"""


@app.get("/v1/pulse/sources")
def sources(x_rapidapi_proxy_secret: str | None = Header(default=None)) -> dict:
    _check_auth(x_rapidapi_proxy_secret)
    data = _load_latest()
    src = data.get("sources", {})
    flat = {k: len(v) for k, v in src.items() if isinstance(v, list)}
    return {
        "generated_at": data["generated_at"],
        "available": {
            **flat,
            "reddit": {k: len(v) for k, v in (src.get("reddit") or {}).items()},
        },
    }


@app.get("/v1/pulse/qiita")
def qiita(x_rapidapi_proxy_secret: str | None = Header(default=None)) -> dict:
    _check_auth(x_rapidapi_proxy_secret)
    data = _load_latest()
    return {"generated_at": data["generated_at"], "items": data["sources"].get("qiita", [])}


@app.get("/v1/pulse/zenn")
def zenn(x_rapidapi_proxy_secret: str | None = Header(default=None)) -> dict:
    _check_auth(x_rapidapi_proxy_secret)
    data = _load_latest()
    return {"generated_at": data["generated_at"], "items": data["sources"].get("zenn", [])}


@app.get("/v1/pulse/devto")
def devto(x_rapidapi_proxy_secret: str | None = Header(default=None)) -> dict:
    _check_auth(x_rapidapi_proxy_secret)
    data = _load_latest()
    return {"generated_at": data["generated_at"], "items": data["sources"].get("devto", [])}


@app.get("/v1/pulse/hatena")
def hatena(x_rapidapi_proxy_secret: str | None = Header(default=None)) -> dict:
    _check_auth(x_rapidapi_proxy_secret)
    data = _load_latest()
    return {"generated_at": data["generated_at"], "items": data["sources"].get("hatena", [])}


@app.get("/v1/pulse/producthunt")
def producthunt(x_rapidapi_proxy_secret: str | None = Header(default=None)) -> dict:
    _check_auth(x_rapidapi_proxy_secret)
    data = _load_latest()
    return {"generated_at": data["generated_at"], "items": data["sources"].get("producthunt", [])}


@app.get("/v1/pulse/arxiv")
def arxiv(x_rapidapi_proxy_secret: str | None = Header(default=None)) -> dict:
    _check_auth(x_rapidapi_proxy_secret)
    data = _load_latest()
    return {"generated_at": data["generated_at"], "items": data["sources"].get("arxiv", [])}


@app.get("/v1/pulse/trending")
def trending(
    limit: int = Query(default=20, ge=1, le=50),
    format: str = Query(default="json", pattern="^(json|csv)$"),
    lang: str | None = Query(default=None, pattern="^(ja|en)$"),
    x_rapidapi_proxy_secret: str | None = Header(default=None),
):
    _check_auth(x_rapidapi_proxy_secret)
    data = _load_latest()
    field = "trending_keywords" if lang is None else f"trending_keywords_{lang}"
    keywords = (data.get(field) or [])[:limit]
    if format == "csv":
        buf = StringIO()
        w = csv.writer(buf)
        w.writerow(["keyword", "count"])
        for k in keywords:
            w.writerow([k["keyword"], k["count"]])
        return PlainTextResponse(buf.getvalue(), media_type="text/csv")
    return {"generated_at": data["generated_at"], "keywords": keywords}


@app.get("/v1/pulse/trending/history")
def trending_history(
    days: int = Query(default=7, ge=2, le=30),
    limit: int = Query(default=20, ge=1, le=50),
    x_rapidapi_proxy_secret: str | None = Header(default=None),
) -> dict:
    """Aggregate keyword counts across the most recent N daily snapshots."""
    _check_auth(x_rapidapi_proxy_secret)
    files = sorted(DATA_DIR.glob("*.json"), reverse=True)[:days]
    if not files:
        raise HTTPException(status_code=503, detail="no snapshots available")
    counter: Counter = Counter()
    per_day: dict[str, list[dict]] = {}
    for path in files:
        snap = json.loads(path.read_text())
        date = path.stem
        per_day[date] = snap.get("trending_keywords") or []
        for k in per_day[date]:
            counter[k["keyword"]] += k["count"]
    overall = [{"keyword": k, "count": c} for k, c in counter.most_common(limit)]
    return {
        "window_days": len(files),
        "overall": overall,
        "per_day": {d: kws[:limit] for d, kws in per_day.items()},
    }


@app.get("/v1/pulse/latest")
def latest(x_rapidapi_proxy_secret: str | None = Header(default=None)) -> dict:
    _check_auth(x_rapidapi_proxy_secret)
    return _load_latest()


@app.get("/v1/pulse/hackernews")
def hackernews(
    limit: int = Query(default=20, ge=1, le=30),
    x_rapidapi_proxy_secret: str | None = Header(default=None),
) -> dict:
    _check_auth(x_rapidapi_proxy_secret)
    data = _load_latest()
    return {"generated_at": data["generated_at"], "items": data["sources"]["hackernews"][:limit]}


@app.get("/v1/pulse/github")
def github(
    language: str | None = Query(default=None),
    x_rapidapi_proxy_secret: str | None = Header(default=None),
) -> dict:
    _check_auth(x_rapidapi_proxy_secret)
    data = _load_latest()
    items = data["sources"]["github_trending"]
    if language:
        items = [r for r in items if (r.get("language") or "").lower() == language.lower()]
    return {"generated_at": data["generated_at"], "items": items}


@app.get("/v1/pulse/reddit/{subreddit}")
def reddit(subreddit: str, x_rapidapi_proxy_secret: str | None = Header(default=None)) -> dict:
    _check_auth(x_rapidapi_proxy_secret)
    data = _load_latest()
    items = data["sources"]["reddit"].get(subreddit)
    if items is None:
        raise HTTPException(status_code=404, detail=f"subreddit '{subreddit}' not tracked")
    return {"generated_at": data["generated_at"], "items": items}


@app.get("/v1/pulse/archive/{date}")
def archive(date: str, x_rapidapi_proxy_secret: str | None = Header(default=None)) -> JSONResponse:
    _check_auth(x_rapidapi_proxy_secret)
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    return JSONResponse(_load_date(date))
