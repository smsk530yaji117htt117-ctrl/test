# -*- coding: utf-8 -*-
"""
notify — 通知ハブ（フォールバック付き通知配送レイヤー）

    res = notify(text, source, level="info", title=None, dedupe_key=None, force_route=None)
    # -> NotifyResult(ok: bool, route: str | None, attempts: list[tuple[route, ok, err]])

- 経路優先順は環境変数 NOTIFY_ROUTES（既定 "discord,slack,notion"）。env 未設定の経路はスキップ。
- 終端は常に notion（ダイジェストページへ Comments API でコメント）。
- notify() は例外を外に投げない（通知失敗で呼び出し元を落とさない）。
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import bridge_notion as bn

DEFAULT_ROUTES = "discord,slack,notion"
DEDUPE_PREFIX = "dedupe_key="

# 経路ごとの必須環境変数（全て設定されていなければ「未設定」としてスキップ）
ROUTE_ENV = {
    "discord": ["DISCORD_WEBHOOK_URL"],
    "slack": ["SLACK_WEBHOOK_URL"],
    "email": ["EMAIL_API_URL", "EMAIL_API_KEY", "EMAIL_TO"],
    "notion": [],  # NOTION_TOKEN を使うが、常時終端として扱う
}


@dataclass
class NotifyResult:
    ok: bool
    route: str | None
    attempts: list = field(default_factory=list)  # list[tuple[route, ok, err]]


# ─── シークレットマスク ───────────────────────────────────────────────────────

_PATTERNS = [
    (r"sk-ant-[A-Za-z0-9\-_]+", "sk-ant-***"),
    (r"sk-proj-[A-Za-z0-9\-_]+", "sk-proj-***"),
    (r"AIza[A-Za-z0-9\-_]+", "AIza***"),
    (r"ntn_[A-Za-z0-9\-_]+", "ntn_***"),
    (r"Bearer\s+[A-Za-z0-9\-_\.]+", "Bearer ***"),
    (r"https://hooks\.slack\.com/services/[^\s\"']+", "https://hooks.slack.com/services/***"),
    (r"https://discord(?:app)?\.com/api/webhooks/[^\s\"']+", "https://discord.com/api/webhooks/***"),
]
_SENSITIVE_ENV_NAMES = {
    "NOTION_TOKEN", "DISCORD_WEBHOOK_URL", "SLACK_WEBHOOK_URL",
    "EMAIL_API_KEY", "EMAIL_API_URL", "EMAIL_TO",
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
}
_SENSITIVE_ENV_PREFIXES = ("ROUTINE_FIRE_TOKEN_", "ROUTINE_FIRE_URL_")


def mask_secrets(text) -> str:
    """既知パターン + 機微 env の実値をマスクして安全なテキストにする"""
    if text is None:
        return ""
    text = str(text)
    for key, val in os.environ.items():
        if not val or len(val) < 6:
            continue
        if key in _SENSITIVE_ENV_NAMES or key.startswith(_SENSITIVE_ENV_PREFIXES):
            text = text.replace(val, "***")
    for pattern, repl in _PATTERNS:
        text = re.sub(pattern, repl, text)
    return text


# ─── 経路判定・整形 ───────────────────────────────────────────────────────────

def _route_configured(route: str) -> bool:
    if route == "notion":
        return True  # 終端は常に利用可能扱い（失敗時は内部でフォールバック記録）
    envs = ROUTE_ENV.get(route)
    if not envs:
        return False
    return all(os.environ.get(e) for e in envs)


def _format(text: str, source: str, level: str, title: str | None) -> str:
    head = f"[{level}]"
    if title:
        head += f" {title}"
    return f"{head}\n{text}\n— source: {source}"


# ─── 各経路の送信 ─────────────────────────────────────────────────────────────

def _send(route: str, text: str, source: str, level: str, title: str | None):
    """(ok, err) を返す。例外は notify() 側でも捕捉するが、ここでも握る。"""
    body = _format(text, source, level, title)
    if route == "discord":
        status, _ = bn.http_post_json(
            os.environ["DISCORD_WEBHOOK_URL"],
            {"Content-Type": "application/json"},
            {"content": body},
        )
        return (200 <= status < 300), None
    if route == "slack":
        status, _ = bn.http_post_json(
            os.environ["SLACK_WEBHOOK_URL"],
            {"Content-Type": "application/json"},
            {"text": body},
        )
        return (200 <= status < 300), None
    if route == "email":
        status, _ = bn.http_post_json(
            os.environ["EMAIL_API_URL"],
            {"Authorization": f"Bearer {os.environ['EMAIL_API_KEY']}",
             "Content-Type": "application/json"},
            {"to": os.environ["EMAIL_TO"], "subject": title or source, "text": body},
        )
        return (200 <= status < 300), None
    if route == "notion":
        return _send_notion(text, source, level, title, body)
    return False, f"未知の経路: {route}"


def _send_notion(text: str, source: str, level: str, title: str | None, body: str):
    """終端: ダイジェストページへコメント。401/403 は Queue 行書き込みを終端とする。"""
    rich: list[dict] = []
    if level == "error":
        rich.append({"type": "mention", "mention": {"type": "user",
                                                     "user": {"id": bn.ERROR_MENTION_USER_ID}}})
        rich.append({"type": "text", "text": {"content": " "}})
    rich.extend(bn.rich_text(body))
    try:
        bn.create_comment(bn.DIGEST_PAGE_ID, rich)
        return True, None
    except bn.HttpError as e:
        if e.status in (401, 403):
            # 権限不足 → Bridge Queue への結果行書き込みを終端とする
            try:
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                bn.create_row(
                    name=f"notify終端記録（notionコメント権限不足） {ts}",
                    action="notify",
                    status="Done",
                    result=f"notion comment {e.status}: コメント権限不足のため Queue 行を終端とした。"
                           f"\n元メッセージ: {body}",
                    payload=text,
                )
                return True, f"notion {e.status}; Queue行に記録(権限不足)"
            except Exception as inner:
                return False, mask_secrets(inner)
        return False, mask_secrets(e)


# ─── dedupe ──────────────────────────────────────────────────────────────────

def _is_duplicate(dedupe_key: str) -> bool:
    marker = f"{DEDUPE_PREFIX}{dedupe_key}"
    for row in bn.query_recent_done(30):
        if marker in bn.row_field(row, "Result"):
            return True
    return False


def _record_dedupe(dedupe_key: str, route: str | None, text: str) -> None:
    """送信成功時に dedupe marker を Queue へ永続化（プロセス毎回終了のため）"""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    bn.create_row(
        name=f"notify dedupe {ts}",
        action="notify",
        status="Done",
        result=f"{DEDUPE_PREFIX}{dedupe_key} route={route}",
        payload=text,
    )


# ─── 公開 API ─────────────────────────────────────────────────────────────────

def notify(text: str, source: str, level: str = "info", title: str | None = None,
           dedupe_key: str | None = None, force_route: str | None = None) -> NotifyResult:
    attempts: list = []

    # dedupe 照会（失敗しても送信は止めない）
    if dedupe_key:
        try:
            if _is_duplicate(dedupe_key):
                return NotifyResult(True, "dedupe",
                                    [("dedupe", True, f"skipped ({DEDUPE_PREFIX}{dedupe_key})")])
        except Exception as e:
            attempts.append(("dedupe", False, mask_secrets(e)))

    if force_route:
        candidates = [force_route]
    else:
        raw = os.environ.get("NOTIFY_ROUTES", DEFAULT_ROUTES)
        candidates = [r.strip() for r in raw.split(",") if r.strip()]
    if "notion" not in candidates:
        candidates.append("notion")  # 終端は常に notion

    for route in candidates:
        if route != "notion" and not _route_configured(route):
            attempts.append((route, False, "env未設定のためスキップ"))
            continue
        try:
            ok, err = _send(route, text, source, level, title)
        except Exception as e:  # notify は例外を外に投げない
            ok, err = False, mask_secrets(e)
        attempts.append((route, ok, err))
        if ok:
            if dedupe_key:
                try:
                    _record_dedupe(dedupe_key, route, text)
                except Exception:
                    pass  # dedupe 記録失敗は送信成功を覆さない
            return NotifyResult(True, route, attempts)

    return NotifyResult(False, None, attempts)
