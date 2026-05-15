"""AI-generated Japanese summaries for each article.

Gated on ANTHROPIC_API_KEY. When unset, the collector skips this step
gracefully and the API simply omits the summary field.

Cost optimization:
- One API call per source (batches all items in one prompt)
- Prompt caching on the stable system prompt (~90% off repeat reads)
- Structured JSON output via output_config.format for reliable parsing
- claude-opus-4-7 by default; override with SUMMARIZE_MODEL env var
"""
from __future__ import annotations

import json
import os
from typing import Iterable

MODEL = os.environ.get("SUMMARIZE_MODEL", "claude-opus-4-7")
MAX_ITEMS_PER_CALL = 25

SYSTEM_PROMPT = """あなたは技術系記事のサマリストです。各記事のタイトルと説明から、日本語の要約を1つ書きます。

ルール:
- 60〜100文字の日本語
- 技術的本質を抽出（ライブラリ名・機能・変更内容など）
- 「すごい」「画期的」のような感情語は避ける
- 体言止めで簡潔に
- 入力された index をそのまま返す

返却JSONスキーマ:
{ "summaries": [ { "index": <int>, "ja": "<60-100文字の日本語>" }, ... ] }"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "summaries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "ja": {"type": "string"},
                },
                "required": ["index", "ja"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["summaries"],
    "additionalProperties": False,
}


def _build_items_block(items: list[dict]) -> str:
    lines = []
    for i, it in enumerate(items[:MAX_ITEMS_PER_CALL]):
        title = it.get("title") or it.get("name") or ""
        ctx = it.get("description") or it.get("abstract") or it.get("url") or ""
        ctx = str(ctx)[:300]
        lines.append(f"[{i}] {title} :: {ctx}")
    return "\n".join(lines)


def _summarize_source(client, source: str, items: list[dict]) -> dict[int, str]:
    if not items:
        return {}
    user = f"以下の {source} 記事を要約してください。\n\n{_build_items_block(items)}"
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        cache_control={"type": "ephemeral"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
    )
    text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), "")
    data = json.loads(text)
    return {s["index"]: s["ja"] for s in data.get("summaries", [])}


def _attach_summaries(items: list[dict], summaries: dict[int, str]) -> None:
    for i, item in enumerate(items[:MAX_ITEMS_PER_CALL]):
        if i in summaries:
            item["summary_ja"] = summaries[i]


def enrich(snapshot: dict) -> dict:
    """Mutate snapshot in place, adding `summary_ja` to each enriched item."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("info: ANTHROPIC_API_KEY not set, skipping summarization")
        return snapshot
    try:
        import anthropic
    except ImportError:
        print("warn: anthropic package not installed, skipping summarization")
        return snapshot

    client = anthropic.Anthropic()
    sources = snapshot.get("sources", {})
    flat: Iterable[tuple[str, list[dict]]] = [
        (k, v) for k, v in sources.items() if isinstance(v, list)
    ]
    flat = list(flat) + [
        (f"reddit/{sub}", posts)
        for sub, posts in (sources.get("reddit") or {}).items()
    ]

    enriched = 0
    for src, items in flat:
        try:
            summaries = _summarize_source(client, src, items)
            _attach_summaries(items, summaries)
            enriched += len(summaries)
        except Exception as exc:
            print(f"warn: summarize {src} failed: {exc}")

    print(f"info: summarized {enriched} items")
    return snapshot
