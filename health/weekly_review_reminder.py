#!/usr/bin/env python3
"""健康OS自動化① — 週次レビューのリマインダー。

毎週日曜 21:00 JST に Notion 健康ログページへコメント（ユーザーメンション付き）を
投稿し、「最新写真を貼って週次レビュー」を促す。

実行基盤は Render Cron / 週次 Routine を想定。本スクリプトは Render 設定・
スケジュールには触れない。有効化（cron 設定・トークン投入）は矢嶋さん承認後に
手動で行う。

必要な環境変数:
- NOTION_TOKEN（健康ログページにコメントできるインテグレーション）
- HEALTH_LOG_PAGE_ID（既定: 37f5ae2b8d6a819784bdf8ac255dbd45）
- REVIEW_MENTION_USER_ID（既定: 173d872b-594c-81b4-af4a-000262688c71 = 矢嶋勇輝）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_HEALTH_LOG_PAGE_ID = "37f5ae2b8d6a819784bdf8ac255dbd45"
DEFAULT_MENTION_USER_ID = "173d872b-594c-81b4-af4a-000262688c71"
NOTION_VERSION = "2022-06-28"
REMINDER_TEXT = (
    " 週次レビューの時間です。最新の顔・上半身の写真をチャットに貼って、"
    "所見＋BMI 推移の追記をリクエストしてください。"
)


class ReminderError(Exception):
    pass


# ----------------------------- 純粋ロジック ----------------------------- #

def build_reminder_comment(user_id: str, text: str = REMINDER_TEXT) -> dict:
    """Notion comments API 用の rich_text ペイロード（先頭にユーザーメンション）。"""
    return {
        "rich_text": [
            {"type": "mention", "mention": {"type": "user", "user": {"id": user_id}}},
            {"type": "text", "text": {"content": text}},
        ]
    }


def is_target_window(now_jst: _dt.datetime) -> bool:
    """日曜 21 時台（JST）かどうかの安全ガード。cron 誤発火時の二重投稿を抑える。"""
    return now_jst.weekday() == 6 and now_jst.hour == 21


def now_jst(now_utc: _dt.datetime | None = None) -> _dt.datetime:
    now_utc = now_utc or _dt.datetime.now(_dt.timezone.utc)
    return now_utc.astimezone(_dt.timezone(_dt.timedelta(hours=9)))


# ----------------------------- ネットワーク ----------------------------- #

def post_comment(notion_token: str, page_id: str, payload: dict) -> dict:
    body = dict(payload)
    body["parent"] = {"page_id": page_id}
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        "https://api.notion.com/v1/comments",
        data=data,
        headers={
            "Authorization": f"Bearer {notion_token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ReminderError(f"Notion comments HTTP {e.code}") from None
    except urllib.error.URLError as e:
        raise ReminderError(f"接続失敗: {e.reason}") from None


# -------------------------------- main -------------------------------- #

def run(dry_run: bool = False, force: bool = False,
        now_utc: _dt.datetime | None = None) -> int:
    if not force and not is_target_window(now_jst(now_utc)):
        print("[skip] 日曜21時台(JST)ではないため何もしません（--force で上書き可）")
        return 0

    page_id = os.environ.get("HEALTH_LOG_PAGE_ID", DEFAULT_HEALTH_LOG_PAGE_ID)
    user_id = os.environ.get("REVIEW_MENTION_USER_ID", DEFAULT_MENTION_USER_ID)
    payload = build_reminder_comment(user_id)

    if dry_run:
        print(f"[dry-run] コメント投稿予定 page={page_id} mention={user_id}")
        return 0

    ntoken = os.environ.get("NOTION_TOKEN")
    if not ntoken:
        raise ReminderError("NOTION_TOKEN が未設定です")
    post_comment(ntoken, page_id, payload)
    print("[ok] リマインダーコメントを投稿しました")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="週次レビューのリマインダー投稿")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="曜日・時刻ガードを無視して投稿する")
    args = parser.parse_args(argv)
    try:
        return run(dry_run=args.dry_run, force=args.force)
    except ReminderError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
