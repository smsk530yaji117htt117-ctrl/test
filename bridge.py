# -*- coding: utf-8 -*-
"""
bridge — 発火リレー + 通知ハブの実行本体

- Bridge Queue DB の Status=Pending を古い順に処理する
  - Action=fire  : Claude Code Routines の API トリガーへ HTTP POST
  - Action=notify: notify() へディスパッチ（Target があれば force_route）
- BRIDGE_SELFTEST=1 のとき、冒頭で全経路 / 全 fire キーへ到達テストを行いレポートする
"""

import os
from datetime import datetime, timezone

import bridge_notion as bn
from notify import notify, mask_secrets

# Claude Code Routines API トリガー仕様（公式: code.claude.com/docs/en/routines）
ROUTINE_BETA_HEADER = "experimental-cc-routine-2026-04-01"
ANTHROPIC_VERSION = "2023-06-01"


# ─── fire（発火リレー）─────────────────────────────────────────────────────────

def _do_fire(target: str, payload: str):
    """(status, result) を返す。status は Done / Error。"""
    key = (target or "").strip()
    if not key:
        return "Error", "Target(ルーチンキー)が空"

    url = os.environ.get(f"ROUTINE_FIRE_URL_{key}")
    token = os.environ.get(f"ROUTINE_FIRE_TOKEN_{key}")
    if not url or not token:
        return "Error", "env未設定"

    headers = {
        "Authorization": f"Bearer {token}",
        "anthropic-beta": ROUTINE_BETA_HEADER,
        "anthropic-version": ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }
    try:
        status, body = bn.http_post_json(url, headers, {"text": payload})
    except bn.HttpError as e:
        return "Error", mask_secrets(f"fire HTTP {e.status}: {e.body}")
    except Exception as e:
        return "Error", mask_secrets(f"fire 例外: {e}")

    if not (200 <= status < 300):
        return "Error", mask_secrets(f"fire HTTP {status}: {body}")

    session_url = body.get("claude_code_session_url", "") if isinstance(body, dict) else ""
    return "Done", f"fired {key}; claude_code_session_url={session_url}"


# ─── notify ディスパッチ ──────────────────────────────────────────────────────

def _do_notify(target: str, payload: str):
    force = (target or "").strip() or None
    res = notify(payload, source="bridge-queue", force_route=force)
    summary = "; ".join(
        f"{r}:{'ok' if ok else 'ng'}" + (f" {mask_secrets(err)}" if err else "")
        for r, ok, err in res.attempts
    )
    if res.ok:
        return "Done", f"route={res.route}; {summary}"
    return "Error", f"全経路失敗; {summary}"


# ─── Queue ポーリング ─────────────────────────────────────────────────────────

def _process_row(row: dict) -> None:
    page_id = row["id"]
    action = bn.row_field(row, "Action")
    target = bn.row_field(row, "Target")
    payload = bn.row_field(row, "Payload")

    try:
        if action == "fire":
            status, result = _do_fire(target, payload)
        elif action == "notify":
            status, result = _do_notify(target, payload)
        else:
            status, result = "Error", f"未知のAction: {action}"
    except Exception as e:
        status, result = "Error", mask_secrets(f"処理中例外: {e}")

    try:
        bn.update_row(page_id, status=status, result=result)
    except Exception as e:
        print(mask_secrets(f"Queue行更新失敗 {page_id[:8]}...: {e}"))


def process_queue() -> int:
    rows = bn.query_pending()
    for row in rows:
        _process_row(row)
    return len(rows)


# ─── SELFTEST ─────────────────────────────────────────────────────────────────

def _configured_fire_keys() -> list[str]:
    prefix = "ROUTINE_FIRE_URL_"
    return sorted({k[len(prefix):] for k in os.environ if k.startswith(prefix)})


def run_selftest() -> str:
    """全経路に1件ずつテスト通知 + 全 fire キーへ text=selftest を POST し、結果を記録する。"""
    lines: list[str] = []

    raw = os.environ.get("NOTIFY_ROUTES", "discord,slack,notion")
    routes = [r.strip() for r in raw.split(",") if r.strip()]
    if "notion" not in routes:
        routes.append("notion")
    for route in routes:
        res = notify(f"selftest {route}", source="SELFTEST", level="info", force_route=route)
        lines.append(f"notify[{route}]: {'ok' if res.ok else 'ng'} (route={res.route})")

    for key in _configured_fire_keys():
        status, result = _do_fire(key, "selftest")
        lines.append(f"fire[{key}]: {status} {mask_secrets(result)}")

    if not _configured_fire_keys():
        lines.append("fire: 設定済みキーなし(ROUTINE_FIRE_URL_* 未設定)")

    summary = "\n".join(lines)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    try:
        bn.create_row(name=f"SELFTEST結果 {ts}", action="notify", status="Done", result=summary)
    except Exception as e:
        print(mask_secrets(f"SELFTEST結果のQueue書き込み失敗: {e}"))
    try:
        bn.create_comment(bn.DIGEST_PAGE_ID, bn.rich_text(f"SELFTEST結果 {ts}\n{summary}"))
    except Exception as e:
        print(mask_secrets(f"SELFTESTコメント書き込み失敗: {e}"))

    return summary


# ─── エントリポイント ─────────────────────────────────────────────────────────

def run() -> None:
    if os.environ.get("BRIDGE_SELFTEST") == "1":
        print("BRIDGE_SELFTEST=1 → セルフテストを実行します")
        run_selftest()
    n = process_queue()
    print(f"bridge: Pending {n}件を処理しました")


if __name__ == "__main__":
    run()
