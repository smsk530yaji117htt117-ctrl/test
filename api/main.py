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


@app.get("/v1/pulse/sources")
def sources(x_rapidapi_proxy_secret: str | None = Header(default=None)) -> dict:
    _check_auth(x_rapidapi_proxy_secret)
    data = _load_latest()
    src = data.get("sources", {})
    return {
        "generated_at": data["generated_at"],
        "available": {
            "hackernews": len(src.get("hackernews", [])),
            "github_trending": len(src.get("github_trending", [])),
            "reddit": {k: len(v) for k, v in (src.get("reddit") or {}).items()},
            "qiita": len(src.get("qiita", [])),
            "zenn": len(src.get("zenn", [])),
            "devto": len(src.get("devto", [])),
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


@app.get("/v1/pulse/trending")
def trending(
    limit: int = Query(default=20, ge=1, le=50),
    format: str = Query(default="json", pattern="^(json|csv)$"),
    x_rapidapi_proxy_secret: str | None = Header(default=None),
):
    _check_auth(x_rapidapi_proxy_secret)
    data = _load_latest()
    keywords = (data.get("trending_keywords") or [])[:limit]
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
