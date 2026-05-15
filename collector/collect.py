"""Daily collector for Tech Pulse API.

Fetches public data from Hacker News, GitHub, and Reddit,
then writes a normalized snapshot into data/daily/YYYY-MM-DD.json.
Runs unattended via GitHub Actions cron.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "daily"
LATEST = ROOT / "data" / "latest.json"

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
GITHUB_SEARCH = "https://api.github.com/search/repositories"
REDDIT_TOP = "https://www.reddit.com/r/{sub}/top.json?t=day&limit=25"

USER_AGENT = "tech-pulse-api/1.0 (+https://github.com/)"
SUBREDDITS = ["programming", "MachineLearning", "webdev"]


def fetch_hn(client: httpx.Client, limit: int = 30) -> list[dict]:
    ids = client.get(HN_TOP, timeout=20).json()[:limit]
    out = []
    for i in ids:
        item = client.get(HN_ITEM.format(id=i), timeout=20).json() or {}
        if item.get("type") != "story":
            continue
        out.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "url": item.get("url") or f"https://news.ycombinator.com/item?id={item.get('id')}",
            "score": item.get("score", 0),
            "comments": item.get("descendants", 0),
            "by": item.get("by"),
            "time": item.get("time"),
        })
    return out


def fetch_github_trending(client: httpx.Client) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    params = {"q": f"pushed:>{since}", "sort": "stars", "order": "desc", "per_page": 25}
    r = client.get(GITHUB_SEARCH, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    items = r.json().get("items", [])
    return [{
        "name": it["full_name"],
        "url": it["html_url"],
        "description": it.get("description"),
        "language": it.get("language"),
        "stars": it.get("stargazers_count", 0),
        "forks": it.get("forks_count", 0),
    } for it in items]


def fetch_reddit(client: httpx.Client, sub: str) -> list[dict]:
    r = client.get(REDDIT_TOP.format(sub=sub), headers={"User-Agent": USER_AGENT}, timeout=20)
    r.raise_for_status()
    children = r.json().get("data", {}).get("children", [])
    return [{
        "title": c["data"].get("title"),
        "url": "https://reddit.com" + c["data"].get("permalink", ""),
        "score": c["data"].get("score", 0),
        "comments": c["data"].get("num_comments", 0),
        "subreddit": sub,
    } for c in children]


def _safe(label: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        print(f"warn: {label} failed: {exc}")
        return [] if label != "reddit" else {}


def build_snapshot() -> dict:
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        reddit_data = {}
        for sub in SUBREDDITS:
            posts = _safe(f"reddit/{sub}", fetch_reddit, client, sub)
            if posts:
                reddit_data[sub] = posts
        snapshot = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": {
                "hackernews": _safe("hackernews", fetch_hn, client),
                "github_trending": _safe("github", fetch_github_trending, client),
                "reddit": reddit_data,
            },
        }
    return snapshot


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    today = datetime.now(timezone.utc).date().isoformat()
    out_path = DATA_DIR / f"{today}.json"
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    LATEST.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
