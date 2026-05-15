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
QIITA_ITEMS = "https://qiita.com/api/v2/items?per_page=25"
ZENN_ARTICLES = "https://zenn.dev/api/articles?order=daily"
DEVTO_ARTICLES = "https://dev.to/api/articles?per_page=25&top=1"

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


def fetch_qiita(client: httpx.Client) -> list[dict]:
    r = client.get(QIITA_ITEMS, timeout=20)
    r.raise_for_status()
    return [{
        "title": it.get("title"),
        "url": it.get("url"),
        "likes": it.get("likes_count", 0),
        "stocks": it.get("stocks_count", 0),
        "tags": [t.get("name") for t in it.get("tags", [])],
        "author": (it.get("user") or {}).get("id"),
    } for it in r.json()]


def fetch_zenn(client: httpx.Client) -> list[dict]:
    r = client.get(ZENN_ARTICLES, timeout=20)
    r.raise_for_status()
    articles = r.json().get("articles", [])
    return [{
        "title": a.get("title"),
        "url": f"https://zenn.dev{a.get('path', '')}",
        "likes": a.get("liked_count", 0),
        "comments": a.get("comments_count", 0),
        "topic": (a.get("publication") or {}).get("name") or a.get("topics"),
    } for a in articles[:25]]


def fetch_devto(client: httpx.Client) -> list[dict]:
    r = client.get(DEVTO_ARTICLES, timeout=20)
    r.raise_for_status()
    return [{
        "title": it.get("title"),
        "url": it.get("url"),
        "reactions": it.get("public_reactions_count", 0),
        "comments": it.get("comments_count", 0),
        "tags": it.get("tag_list", []),
        "author": (it.get("user") or {}).get("username"),
    } for it in r.json()]


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
                "qiita": _safe("qiita", fetch_qiita, client),
                "zenn": _safe("zenn", fetch_zenn, client),
                "devto": _safe("devto", fetch_devto, client),
            },
        }
    snapshot["trending_keywords"] = compute_keywords(snapshot["sources"])
    return snapshot


_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do",
    "does", "did", "this", "that", "these", "those", "it", "its", "i", "you", "we",
    "they", "he", "she", "as", "at", "by", "from", "how", "what", "why", "when",
    "where", "your", "my", "our", "their", "his", "her", "all", "any", "new", "use",
    "using", "used", "can", "will", "not", "no", "yes", "into", "out", "up", "down",
    "more", "most", "less", "least", "than", "vs", "via", "about", "after", "before",
}


def compute_keywords(sources: dict, top_n: int = 25) -> list[dict]:
    import re
    from collections import Counter
    counter: Counter = Counter()
    def add_text(items, fields):
        for it in items or []:
            if not isinstance(it, dict):
                continue
            text = " ".join(str(it.get(f) or "") for f in fields)
            for tok in re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]{1,}", text.lower()):
                if tok in _STOPWORDS or len(tok) < 3:
                    continue
                counter[tok] += 1
    add_text(sources.get("hackernews"), ["title"])
    add_text(sources.get("github_trending"), ["name", "description"])
    add_text(sources.get("qiita"), ["title"])
    add_text(sources.get("zenn"), ["title"])
    add_text(sources.get("devto"), ["title"])
    for posts in (sources.get("reddit") or {}).values():
        add_text(posts, ["title"])
    return [{"keyword": k, "count": c} for k, c in counter.most_common(top_n)]


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
