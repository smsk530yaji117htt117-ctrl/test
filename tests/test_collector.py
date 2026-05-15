"""Unit tests for collector helpers."""
from collector.collect import compute_keywords
from collector.webhook import _detect_surges


def test_keywords_count_across_sources():
    sources = {
        "hackernews": [{"title": "Rust is fast and Rust is safe"}],
        "github_trending": [{"name": "rust-lang/runtime", "description": "rust async runtime"}],
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


def test_keywords_lang_filter():
    sources = {
        "hackernews": [{"title": "rust async"}],
        "qiita": [{"title": "python tips"}],
        "hatena": [{"title": "python news"}],
    }
    en = compute_keywords(sources, lang="en")
    ja = compute_keywords(sources, lang="ja")
    en_keys = {k["keyword"] for k in en}
    ja_keys = {k["keyword"] for k in ja}
    assert "rust" in en_keys and "rust" not in ja_keys
    assert "python" in ja_keys


def test_surge_detect_new_entrant():
    today = [{"keyword": "rust", "count": 5}, {"keyword": "go", "count": 3}]
    prev = {"go": 2}
    surges = _detect_surges(today, prev)
    kinds = {s["keyword"]: s["kind"] for s in surges}
    assert kinds.get("rust") == "new"


def test_surge_detect_doubled():
    today = [{"keyword": "rust", "count": 10}]
    prev = {"rust": 4}
    surges = _detect_surges(today, prev)
    assert surges and surges[0]["kind"] == "surge"


def test_surge_skips_modest_growth():
    today = [{"keyword": "rust", "count": 6}]
    prev = {"rust": 5}
    assert _detect_surges(today, prev) == []
