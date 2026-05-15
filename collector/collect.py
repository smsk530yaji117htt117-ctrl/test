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
HATENA_RSS = "https://b.hatena.ne.jp/hotentry/it.rss"
PRODUCTHUNT_RSS = "https://www.producthunt.com/feed"
ARXIV_API = "https://export.arxiv.org/api/query"

USER_AGENT = "tech-pulse-api/1.0 (+https://github.com/)"
SUBREDDITS = ["programming", "MachineLearning", "webdev"]
ARXIV_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL"]
JAPANESE_SOURCES = {"qiita", "zenn", "hatena"}


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


def fetch_hatena(client: httpx.Client) -> list[dict]:
    import xml.etree.ElementTree as ET
    r = client.get(HATENA_RSS, timeout=20)
    r.raise_for_status()
    ns = {
        "rss": "http://purl.org/rss/1.0/",
        "dc": "http://purl.org/dc/elements/1.1/",
        "hatena": "http://www.hatena.ne.jp/info/xmlns#",
    }
    root = ET.fromstring(r.content)
    items = []
    for item in root.findall("rss:item", ns):
        title = item.findtext("rss:title", default="", namespaces=ns)
        url = item.findtext("rss:link", default="", namespaces=ns)
        bookmarks = item.findtext("hatena:bookmarkcount", default="0", namespaces=ns)
        items.append({
            "title": title,
            "url": url,
            "bookmarks": int(bookmarks) if bookmarks.isdigit() else 0,
        })
    return items[:25]


def fetch_producthunt(client: httpx.Client) -> list[dict]:
    import xml.etree.ElementTree as ET
    r = client.get(PRODUCTHUNT_RSS, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    channel = root.find("channel")
    out = []
    if channel is None:
        return out
    for item in channel.findall("item")[:25]:
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        out.append({"title": title, "url": url, "description": description})
    return out


def fetch_arxiv(client: httpx.Client) -> list[dict]:
    import xml.etree.ElementTree as ET
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    out = []
    query = "+OR+".join(f"cat:{c}" for c in ARXIV_CATEGORIES)
    params = {
        "search_query": query,
        "max_results": 25,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    r = client.get(ARXIV_API, params=params, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
        link = ""
        for l in entry.findall("atom:link", ns):
            if l.attrib.get("rel") == "alternate":
                link = l.attrib.get("href", "")
                break
        authors = [
            (a.findtext("atom:name", default="", namespaces=ns) or "").strip()
            for a in entry.findall("atom:author", ns)
        ]
        out.append({
            "title": " ".join(title.split()),
            "url": link,
            "abstract": " ".join(summary.split())[:400],
            "authors": authors[:5],
        })
    return out


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
                "hatena": _safe("hatena", fetch_hatena, client),
                "producthunt": _safe("producthunt", fetch_producthunt, client),
                "arxiv": _safe("arxiv", fetch_arxiv, client),
            },
        }
    snapshot["trending_keywords"] = compute_keywords(snapshot["sources"])
    snapshot["trending_keywords_ja"] = compute_keywords(snapshot["sources"], lang="ja")
    snapshot["trending_keywords_en"] = compute_keywords(snapshot["sources"], lang="en")
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


_SOURCE_FIELDS = {
    "hackernews": ["title"],
    "github_trending": ["name", "description"],
    "qiita": ["title"],
    "zenn": ["title"],
    "devto": ["title"],
    "hatena": ["title"],
    "producthunt": ["title", "description"],
    "arxiv": ["title"],
}


def compute_keywords(sources: dict, top_n: int = 25, lang: str | None = None) -> list[dict]:
    """Top keywords across titles.

    `lang` filters which sources contribute:
      - None: all sources
      - "ja": Japanese sources only (qiita / zenn / hatena)
      - "en": non-Japanese sources
    """
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
    for src, fields in _SOURCE_FIELDS.items():
        if lang == "ja" and src not in JAPANESE_SOURCES:
            continue
        if lang == "en" and src in JAPANESE_SOURCES:
            continue
        add_text(sources.get(src), fields)
    if lang != "ja":
        for posts in (sources.get("reddit") or {}).values():
            add_text(posts, ["title"])
    return [{"keyword": k, "count": c} for k, c in counter.most_common(top_n)]


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()

    from collector import summarize, webhook
    summarize.enrich(snapshot)
    webhook.notify(snapshot)

    today = datetime.now(timezone.utc).date().isoformat()
    out_path = DATA_DIR / f"{today}.json"
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    LATEST.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
