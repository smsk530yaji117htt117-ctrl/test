"""End-to-end tests for the API.

Uses a fixture snapshot so tests don't depend on the live collector.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = {
    "generated_at": "2026-05-15T00:00:00+00:00",
    "sources": {
        "hackernews": [{"id": 1, "title": "Rust beats Python", "url": "https://x", "score": 100, "comments": 10, "summary_ja": "RustがPythonを上回る性能テスト結果"}],
        "github_trending": [
            {"name": "owner/py-repo", "url": "https://x", "language": "Python", "stars": 50, "forks": 5},
            {"name": "owner/rs-repo", "url": "https://x", "language": "Rust", "stars": 80, "forks": 8},
        ],
        "reddit": {"programming": [{"title": "Rust is fast", "url": "https://x", "score": 10, "comments": 1, "subreddit": "programming"}]},
        "qiita": [{"title": "Python tips", "url": "https://x", "likes": 5, "stocks": 2, "tags": ["Python"]}],
        "zenn": [{"title": "Zenn article", "url": "https://x", "likes": 3, "comments": 0}],
        "devto": [{"title": "Dev post", "url": "https://x", "reactions": 7, "comments": 2, "tags": ["python"]}],
        "hatena": [{"title": "Hatena post", "url": "https://x", "bookmarks": 42}],
        "producthunt": [{"title": "PH product", "url": "https://x", "description": "A new tool"}],
        "arxiv": [{"title": "LLM paper", "url": "https://x", "abstract": "We study LLMs.", "authors": ["A"]}],
    },
    "trending_keywords": [{"keyword": "rust", "count": 2}, {"keyword": "python", "count": 2}],
    "trending_keywords_ja": [{"keyword": "python", "count": 1}],
    "trending_keywords_en": [{"keyword": "rust", "count": 2}],
}


@pytest.fixture(autouse=True)
def seed(tmp_path, monkeypatch):
    data_dir = ROOT / "data"
    daily = data_dir / "daily"
    daily.mkdir(parents=True, exist_ok=True)
    latest = data_dir / "latest.json"
    backup_latest = latest.read_text() if latest.exists() else None
    backup_archive = daily / "2026-05-15.json"
    backup_archive_data = backup_archive.read_text() if backup_archive.exists() else None
    latest.write_text(json.dumps(FIXTURE))
    backup_archive.write_text(json.dumps(FIXTURE))
    yield
    if backup_latest is not None:
        latest.write_text(backup_latest)
    if backup_archive_data is not None:
        backup_archive.write_text(backup_archive_data)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("RAPIDAPI_PROXY_SECRET", raising=False)
    from api import main as api_main
    api_main.RAPIDAPI_SECRET = None
    return TestClient(api_main.app)


@pytest.fixture
def authed_client(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_PROXY_SECRET", "secret")
    from api import main as api_main
    api_main.RAPIDAPI_SECRET = "secret"
    return TestClient(api_main.app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_landing(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Tech Pulse API" in r.text


def test_latest(client):
    r = client.get("/v1/pulse/latest")
    assert r.status_code == 200
    assert "sources" in r.json()


def test_sources_summary(client):
    r = client.get("/v1/pulse/sources")
    assert r.status_code == 200
    avail = r.json()["available"]
    assert avail["hackernews"] == 1
    assert avail["github_trending"] == 2


def test_github_filter_by_language(client):
    r = client.get("/v1/pulse/github?language=python")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["language"] == "Python"


def test_hn_limit(client):
    r = client.get("/v1/pulse/hackernews?limit=1")
    assert r.status_code == 200 and len(r.json()["items"]) == 1


def test_reddit_missing(client):
    r = client.get("/v1/pulse/reddit/nope")
    assert r.status_code == 404


def test_archive_valid(client):
    r = client.get("/v1/pulse/archive/2026-05-15")
    assert r.status_code == 200


def test_archive_bad_date(client):
    r = client.get("/v1/pulse/archive/not-a-date")
    assert r.status_code == 400


def test_trending(client):
    r = client.get("/v1/pulse/trending?limit=5")
    assert r.status_code == 200 and len(r.json()["keywords"]) <= 5


def test_trending_csv(client):
    r = client.get("/v1/pulse/trending?format=csv&limit=2")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0] == "keyword,count"
    assert len(lines) <= 3  # header + up to 2 rows


def test_trending_history(client):
    r = client.get("/v1/pulse/trending/history?days=2&limit=10")
    assert r.status_code == 200
    body = r.json()
    assert "overall" in body and "per_day" in body
    assert body["window_days"] >= 1


def test_qiita_zenn_devto(client):
    for path in ["/v1/pulse/qiita", "/v1/pulse/zenn", "/v1/pulse/devto"]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert "items" in r.json(), path


def test_new_sources(client):
    for path in ["/v1/pulse/hatena", "/v1/pulse/producthunt", "/v1/pulse/arxiv"]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert "items" in r.json(), path


def test_trending_lang_ja(client):
    r = client.get("/v1/pulse/trending?lang=ja")
    assert r.status_code == 200
    kws = r.json()["keywords"]
    assert any(k["keyword"] == "python" for k in kws)


def test_trending_lang_en(client):
    r = client.get("/v1/pulse/trending?lang=en")
    assert r.status_code == 200
    kws = r.json()["keywords"]
    assert any(k["keyword"] == "rust" for k in kws)


def test_trending_lang_invalid_rejected(client):
    r = client.get("/v1/pulse/trending?lang=fr")
    assert r.status_code == 422


def test_dashboard(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "Tech Pulse" in r.text
    assert "rust" in r.text  # trending keyword shows up
    assert "hatena" in r.text  # source listed


def test_sources_includes_new(client):
    r = client.get("/v1/pulse/sources")
    avail = r.json()["available"]
    for k in ("hatena", "producthunt", "arxiv"):
        assert k in avail, k


def test_auth_missing_when_required(authed_client):
    r = authed_client.get("/v1/pulse/latest")
    assert r.status_code == 401


def test_auth_correct(authed_client):
    r = authed_client.get("/v1/pulse/latest", headers={"X-RapidAPI-Proxy-Secret": "secret"})
    assert r.status_code == 200


def test_health_open_even_when_secret_set(authed_client):
    r = authed_client.get("/health")
    assert r.status_code == 200
