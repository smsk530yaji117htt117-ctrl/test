"""Webhook notifications for keyword surges.

When TECH_PULSE_WEBHOOK_URL is set, compares today's top keywords
against yesterday's snapshot and POSTs notable changes to the URL.
Compatible with Slack/Discord incoming-webhook payloads (just a `text` field).

A keyword "surges" if it's in today's top 15 and either:
  - was absent from yesterday's top 15 (a new entrant), or
  - its count at least doubled vs yesterday
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "daily"

TOP_N = 15
SURGE_MULTIPLIER = 2.0


def _load_previous_keywords() -> dict[str, int]:
    files = sorted(DATA_DIR.glob("*.json"), reverse=True)
    if len(files) < 2:
        return {}
    prev = json.loads(files[1].read_text())
    kws = prev.get("trending_keywords") or []
    return {k["keyword"]: k["count"] for k in kws[:TOP_N]}


def _detect_surges(today: list[dict], previous: dict[str, int]) -> list[dict]:
    surges = []
    for entry in today[:TOP_N]:
        kw, count = entry["keyword"], entry["count"]
        prev_count = previous.get(kw, 0)
        if prev_count == 0:
            surges.append({"keyword": kw, "count": count, "prev": 0, "kind": "new"})
        elif count >= prev_count * SURGE_MULTIPLIER:
            surges.append({"keyword": kw, "count": count, "prev": prev_count, "kind": "surge"})
    return surges


def _format_message(surges: list[dict], generated_at: str) -> str:
    if not surges:
        return ""
    lines = [f"*Tech Pulse* — keyword surges for {generated_at[:10]}"]
    for s in surges[:10]:
        if s["kind"] == "new":
            lines.append(f"• `{s['keyword']}` (new entrant, count={s['count']})")
        else:
            lines.append(f"• `{s['keyword']}` ({s['prev']} → {s['count']})")
    return "\n".join(lines)


def notify(snapshot: dict) -> None:
    url = os.environ.get("TECH_PULSE_WEBHOOK_URL")
    if not url:
        print("info: TECH_PULSE_WEBHOOK_URL not set, skipping webhook")
        return
    keywords = snapshot.get("trending_keywords") or []
    previous = _load_previous_keywords()
    surges = _detect_surges(keywords, previous)
    if not surges:
        print("info: no surges detected, no webhook sent")
        return
    text = _format_message(surges, snapshot.get("generated_at", ""))
    try:
        r = httpx.post(url, json={"text": text, "surges": surges}, timeout=15)
        r.raise_for_status()
        print(f"info: webhook sent ({len(surges)} surges)")
    except Exception as exc:
        print(f"warn: webhook failed: {exc}")
