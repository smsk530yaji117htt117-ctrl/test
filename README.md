# Tech Pulse API

Daily aggregated tech trends from public sources — designed as a sell-on-RapidAPI data product.

- **Sources:** Hacker News, GitHub Trending, Reddit (r/programming, r/MachineLearning, r/webdev)
- **Update cadence:** Daily, fully automated via GitHub Actions
- **Hosting:** Vercel Python serverless (free tier)
- **Monetization:** RapidAPI marketplace handles auth + billing + payouts

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
| GET | `/v1/pulse/latest` | Full latest snapshot |
| GET | `/v1/pulse/hackernews?limit=20` | Top HN stories |
| GET | `/v1/pulse/github?language=Python` | GitHub repos created today |
| GET | `/v1/pulse/reddit/{subreddit}` | Top posts from tracked subreddit |
| GET | `/v1/pulse/archive/{YYYY-MM-DD}` | Historical snapshot |
| GET | `/health` | Liveness check (unauthenticated) |

All endpoints except `/health` require `X-RapidAPI-Proxy-Secret` in production
so only RapidAPI's proxy can call them.
