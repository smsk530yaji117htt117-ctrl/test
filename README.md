# Tech Pulse API

Daily aggregated tech trends from public sources — designed as a sell-on-RapidAPI data product.

- **Sources:** Hacker News, GitHub Trending, Reddit (r/programming, r/MachineLearning, r/webdev), Qiita, Zenn, Dev.to
- **Trend extraction:** Top keywords computed across all titles each day
- **Update cadence:** Daily, fully automated via GitHub Actions
- **Hosting:** Vercel Python serverless (free tier)
- **Monetization:** RapidAPI marketplace handles auth + billing + payouts
- **Quality:** 16 pytest tests run in CI on every push

## Quick start (local)

```bash
pip install -r requirements.txt
python collector/collect.py          # writes data/latest.json
uvicorn api.main:app --reload        # serves on :8000
curl http://localhost:8000/v1/pulse/latest
```

## Deploy & monetize

See [SETUP.md](./SETUP.md) for the full one-time setup (Vercel + RapidAPI).

## Layout

```
api/main.py              FastAPI app (5 endpoints)
collector/collect.py     Daily public-data fetcher
.github/workflows/       Cron + auto-commit snapshot
data/latest.json         Latest snapshot served by the API
data/daily/*.json        Archive (queryable via /v1/pulse/archive/{date})
vercel.json              Serverless deployment config
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | HTML landing page (marketing / SEO) |
| GET | `/v1/pulse/latest` | Full latest snapshot |
| GET | `/v1/pulse/sources` | Item counts per source |
| GET | `/v1/pulse/trending?limit=20` | Top keywords across all titles today |
| GET | `/v1/pulse/hackernews?limit=20` | Top HN stories |
| GET | `/v1/pulse/github?language=Python` | GitHub trending repos (optional filter) |
| GET | `/v1/pulse/reddit/{subreddit}` | Top posts from tracked subreddit |
| GET | `/v1/pulse/qiita` | Qiita latest items (Japan) |
| GET | `/v1/pulse/zenn` | Zenn daily articles (Japan) |
| GET | `/v1/pulse/devto` | Dev.to top articles |
| GET | `/v1/pulse/archive/{YYYY-MM-DD}` | Historical snapshot |
| GET | `/health` | Liveness check (unauthenticated) |

All endpoints except `/` and `/health` require `X-RapidAPI-Proxy-Secret` in
production so only RapidAPI's proxy can call them.

## Consumer examples

Once listed on RapidAPI, clients call via the marketplace proxy:

```bash
curl -H "X-RapidAPI-Key: $KEY" \
     -H "X-RapidAPI-Host: tech-pulse-api.p.rapidapi.com" \
     https://tech-pulse-api.p.rapidapi.com/v1/pulse/trending
```

```python
import httpx
r = httpx.get(
    "https://tech-pulse-api.p.rapidapi.com/v1/pulse/trending/history",
    params={"days": 7, "limit": 10},
    headers={"X-RapidAPI-Key": KEY, "X-RapidAPI-Host": "tech-pulse-api.p.rapidapi.com"},
)
print(r.json()["overall"])
```

```javascript
const res = await fetch("https://tech-pulse-api.p.rapidapi.com/v1/pulse/github?language=Rust", {
  headers: { "X-RapidAPI-Key": KEY, "X-RapidAPI-Host": "tech-pulse-api.p.rapidapi.com" },
});
console.log(await res.json());
```

## OpenAPI

`docs/openapi.json` is a committed snapshot of the live schema. Upload it on
RapidAPI to import every endpoint at once. CI fails if the snapshot drifts from
the code — run `python scripts/export_openapi.py` after changing endpoints.
