"""Unit tests for keyword extraction in the collector."""
from collector.collect import compute_keywords


def test_keywords_count_across_sources():
    sources = {
        "hackernews": [{"title": "Rust is fast and Rust is safe"}],
        "github_trending": [{"title": "rust async runtime"}],
        "reddit": {"programming": [{"title": "Rust beats Python"}]},
        "qiita": [{"title": "PythonでRustを呼ぶ"}],
        "zenn": [],
        "devto": [{"title": "python tips"}],
    }
    kws = compute_keywords(sources)
    by_key = {k["keyword"]: k["count"] for k in kws}
    assert by_key.get("rust", 0) >= 3
    assert by_key.get("python", 0) >= 2


def test_keywords_skip_stopwords_and_short():
    sources = {"hackernews": [{"title": "the and to of in on"}]}
    assert compute_keywords(sources) == []


def test_keywords_handles_empty():
    assert compute_keywords({}) == []
