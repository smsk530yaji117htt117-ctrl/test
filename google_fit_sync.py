#!/usr/bin/env python3
"""Google Fit -> Notion 50_Daily 同期スクリプト.

PersonalOS の Render Cron で毎日 07:00 JST に実行され、Google Fit REST API
(fitness.v1) から指定日の体重・歩数・消費カロリーを取得し、Notion の
50_Daily データベースへ書き込む。

設計方針
--------
- 秘匿情報 (client_id / client_secret / refresh_token / api_key) はすべて
  環境変数から取得する。ハードコード厳禁。
- token / secret / api_key の値は **一切ログに出力しない**。
  例外処理でも HTTP ステータスと Google/Notion が返すエラーコード
  (例: ``invalid_grant``) のみを記録する。
- refresh token の失効 (``invalid_grant``) を専用例外として判別し、
  「再認証が必要」である旨を明確に通知する (恒久対策は OAuth 同意画面の
  本番公開。docs/google_fit_oauth_setup.md を参照)。

使い方
------
    python google_fit_sync.py                 # 前日(JST)分を同期 (07:00 cron 既定)
    python google_fit_sync.py --date 2026-05-30
    python google_fit_sync.py --today         # 当日(JST)分を対象にする
    python google_fit_sync.py --dry-run       # 取得のみ。Notion へは書き込まない
                                              # (= 再認証後の最小検証に使用)

終了コード
----------
    0  正常終了
    2  refresh token 失効 (要・再認証)
    1  その他のエラー
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

# --- 定数 -----------------------------------------------------------------

JST = ZoneInfo("Asia/Tokyo")

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
FITNESS_AGGREGATE_URL = (
    "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"
)
NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Google Fit データ型
DT_STEPS = "com.google.step_count.delta"
DT_CALORIES = "com.google.calories.expended"
DT_WEIGHT_SUMMARY = "com.google.weight.summary"

# Notion 50_Daily のプロパティ名。
# NOTE: 既存スキーマに合わせて環境変数で上書き可能にしている。Notion スキーマ
#       自体は変更しないこと (Do Not Touch)。レビュー時に既存 50_Daily の
#       プロパティ名と一致しているか確認すること。
PROP_DATE = os.environ.get("NOTION_50_DAILY_DATE_PROP", "日付")
PROP_WEIGHT = os.environ.get("NOTION_50_DAILY_WEIGHT_PROP", "体重")
PROP_STEPS = os.environ.get("NOTION_50_DAILY_STEPS_PROP", "歩数")
PROP_CALORIES = os.environ.get("NOTION_50_DAILY_CALORIES_PROP", "消費カロリー")

logger = logging.getLogger("google_fit_sync")


# --- 例外 -----------------------------------------------------------------


class GoogleFitSyncError(Exception):
    """このスクリプト共通の基底例外."""


class RefreshTokenExpiredError(GoogleFitSyncError):
    """refresh token が失効している (invalid_grant)。再認証が必要."""


# --- 小さなユーティリティ ---------------------------------------------------


def require_env(name: str) -> str:
    """必須の環境変数を取得する。未設定なら明確なエラーを送出する。

    値そのものはログに出さない (名前のみ)。
    """
    value = os.environ.get(name)
    if not value:
        raise GoogleFitSyncError(
            f"必須の環境変数 {name} が未設定です。Render の環境変数を確認してください。"
        )
    return value


def _post_json(
    url: str,
    *,
    data: Optional[dict] = None,
    form: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: int = 30,
) -> tuple[int, dict]:
    """JSON / form を POST し ``(status_code, parsed_json_body)`` を返す.

    秘匿情報を含み得るため、リクエストボディは決してログに出さない。
    HTTPError でも本文の JSON だけを返し、呼び出し側がエラーコードを判定する。
    """
    headers = dict(headers or {})
    if form is not None:
        body = "&".join(
            f"{_url_quote(k)}={_url_quote(v)}" for k, v in form.items()
        ).encode("utf-8")
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    else:
        body = json.dumps(data or {}).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, _read_json(resp)
    except urllib.error.HTTPError as exc:  # 4xx / 5xx
        parsed = _read_json(exc) or {}
        return exc.code, parsed


def _get_json(url: str, *, headers: dict, timeout: int = 30) -> tuple[int, dict]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, _read_json(resp)
    except urllib.error.HTTPError as exc:
        return exc.code, (_read_json(exc) or {})


def _read_json(resp: Any) -> dict:
    try:
        raw = resp.read().decode("utf-8")
    except Exception:  # noqa: BLE001 - 読めなければ空扱い
        return {}
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 本文が JSON でない場合でも秘匿情報を晒さないよう、生本文は返さない。
        return {}


def _url_quote(value: str) -> str:
    from urllib.parse import quote

    return quote(str(value), safe="")


# --- Google OAuth ---------------------------------------------------------


def refresh_access_token(
    client_id: str, client_secret: str, refresh_token: str
) -> str:
    """refresh token から access token を取得する.

    失効時 (``invalid_grant``) は :class:`RefreshTokenExpiredError` を送出する。
    レスポンス本文・リクエスト本文ともに秘匿情報をログへ出力しない。
    """
    status, payload = _post_json(
        GOOGLE_TOKEN_URL,
        form={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )

    if status == 200 and payload.get("access_token"):
        logger.info("access token を更新しました (HTTP 200)。")
        return payload["access_token"]

    # 失敗。Google が返す error コードのみを使う (秘匿情報は含まれない)。
    error = payload.get("error", "unknown_error")
    description = payload.get("error_description", "")
    if error == "invalid_grant":
        raise RefreshTokenExpiredError(
            "refresh token が失効しています (invalid_grant: "
            f"{description or 'Token has been expired or revoked.'})。"
            " 再認証が必要です。docs/google_fit_oauth_setup.md の手順に従って"
            " OAuth 同意画面を本番公開し、google_fit_reauth.py で新しい"
            " refresh token を取得してください。"
        )
    raise GoogleFitSyncError(
        f"access token の取得に失敗しました (HTTP {status}, error={error})。"
    )


# --- Google Fit データ取得 -------------------------------------------------


def _aggregate(access_token: str, data_type: str, start_ms: int, end_ms: int) -> dict:
    status, payload = _post_json(
        FITNESS_AGGREGATE_URL,
        data={
            "aggregateBy": [{"dataTypeName": data_type}],
            "bucketByTime": {"durationMillis": end_ms - start_ms},
            "startTimeMillis": start_ms,
            "endTimeMillis": end_ms,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if status != 200:
        error = payload.get("error", {})
        message = error.get("message") if isinstance(error, dict) else error
        raise GoogleFitSyncError(
            f"Google Fit 集計取得に失敗 (data_type={data_type}, "
            f"HTTP {status}, message={message})。"
        )
    return payload


def _iter_points(aggregate_payload: dict):
    for bucket in aggregate_payload.get("bucket", []):
        for dataset in bucket.get("dataset", []):
            for point in dataset.get("point", []):
                yield point


def get_steps(access_token: str, start_ms: int, end_ms: int) -> Optional[int]:
    payload = _aggregate(access_token, DT_STEPS, start_ms, end_ms)
    total = 0
    found = False
    for point in _iter_points(payload):
        for value in point.get("value", []):
            if "intVal" in value:
                total += int(value["intVal"])
                found = True
    return total if found else None


def get_calories(access_token: str, start_ms: int, end_ms: int) -> Optional[float]:
    payload = _aggregate(access_token, DT_CALORIES, start_ms, end_ms)
    total = 0.0
    found = False
    for point in _iter_points(payload):
        for value in point.get("value", []):
            if "fpVal" in value:
                total += float(value["fpVal"])
                found = True
    return round(total, 1) if found else None


def get_weight(access_token: str, start_ms: int, end_ms: int) -> Optional[float]:
    """体重(kg)を取得する。

    com.google.weight.summary の value は [average, max, min] (fpVal)。
    その日の平均値を採用する。データが無ければ None。
    """
    payload = _aggregate(access_token, DT_WEIGHT_SUMMARY, start_ms, end_ms)
    latest: Optional[float] = None
    for point in _iter_points(payload):
        values = point.get("value", [])
        if values and "fpVal" in values[0]:
            latest = round(float(values[0]["fpVal"]), 1)  # average
    return latest


def fetch_day_summary(access_token: str, date: datetime) -> dict:
    """指定日(JST)の体重・歩数・消費カロリーを取得する。"""
    start = date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=JST)
    end = start + timedelta(days=1)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    summary = {
        "weight": get_weight(access_token, start_ms, end_ms),
        "steps": get_steps(access_token, start_ms, end_ms),
        "calories": get_calories(access_token, start_ms, end_ms),
    }
    logger.info(
        "取得結果 %s: weight=%s steps=%s calories=%s",
        start.date().isoformat(),
        summary["weight"],
        summary["steps"],
        summary["calories"],
    )
    return summary


# --- Notion 書き込み -------------------------------------------------------


def _notion_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _notion_find_page(api_key: str, db_id: str, date_iso: str) -> Optional[str]:
    """日付に一致する既存ページの id を返す (無ければ None)。"""
    status, payload = _post_json(
        f"{NOTION_API_BASE}/databases/{db_id}/query",
        data={
            "filter": {"property": PROP_DATE, "date": {"equals": date_iso}},
            "page_size": 1,
        },
        headers=_notion_headers(api_key),
    )
    if status != 200:
        raise GoogleFitSyncError(
            f"Notion クエリに失敗 (HTTP {status})。50_Daily DB の id と "
            "プロパティ名を確認してください。"
        )
    results = payload.get("results", [])
    return results[0]["id"] if results else None


def _build_properties(date_iso: str, summary: dict) -> dict:
    props: dict[str, Any] = {
        PROP_DATE: {"date": {"start": date_iso}},
    }
    if summary.get("weight") is not None:
        props[PROP_WEIGHT] = {"number": summary["weight"]}
    if summary.get("steps") is not None:
        props[PROP_STEPS] = {"number": summary["steps"]}
    if summary.get("calories") is not None:
        props[PROP_CALORIES] = {"number": summary["calories"]}
    return props


def write_to_notion(api_key: str, db_id: str, date_iso: str, summary: dict) -> None:
    """50_Daily に upsert する (同日付があれば更新、無ければ作成)。"""
    properties = _build_properties(date_iso, summary)
    page_id = _notion_find_page(api_key, db_id, date_iso)

    if page_id:
        status, _ = _patch_json(
            f"{NOTION_API_BASE}/pages/{page_id}",
            data={"properties": properties},
            headers=_notion_headers(api_key),
        )
        action = "更新"
    else:
        status, _ = _post_json(
            f"{NOTION_API_BASE}/pages",
            data={"parent": {"database_id": db_id}, "properties": properties},
            headers=_notion_headers(api_key),
        )
        action = "作成"

    if status not in (200, 201):
        raise GoogleFitSyncError(f"Notion への{action}に失敗 (HTTP {status})。")
    logger.info("Notion 50_Daily を%sしました (%s)。", action, date_iso)


def _patch_json(url: str, *, data: dict, headers: dict, timeout: int = 30):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, _read_json(resp)
    except urllib.error.HTTPError as exc:
        return exc.code, (_read_json(exc) or {})


# --- エントリポイント -------------------------------------------------------


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Google Fit -> Notion 50_Daily 同期")
    parser.add_argument("--date", help="同期対象日 (YYYY-MM-DD, JST)。既定は前日。")
    parser.add_argument(
        "--today", action="store_true", help="当日(JST)を対象にする (既定は前日)。"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Google Fit から取得するのみで Notion へは書き込まない (検証用)。",
    )
    return parser.parse_args(argv)


def resolve_date(args: argparse.Namespace) -> datetime:
    if args.date:
        return datetime.strptime(args.date, "%Y-%m-%d")
    now = datetime.now(JST)
    if not args.today:
        # 既定は前日分。07:00 JST の cron で前日の完全なデータを取得するため。
        now = now - timedelta(days=1)
    return datetime(now.year, now.month, now.day)


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args(argv)

    try:
        date = resolve_date(args)
        date_iso = date.date().isoformat()

        client_id = require_env("GOOGLE_FIT_CLIENT_ID")
        client_secret = require_env("GOOGLE_FIT_CLIENT_SECRET")
        refresh_token = require_env("GOOGLE_FIT_REFRESH_TOKEN")

        access_token = refresh_access_token(client_id, client_secret, refresh_token)
        summary = fetch_day_summary(access_token, date)

        if args.dry_run:
            logger.info(
                "dry-run のため Notion へは書き込みません。取得は成功です (HTTP 200)。"
            )
            print(json.dumps({"date": date_iso, **summary}, ensure_ascii=False))
            return 0

        notion_api_key = require_env("NOTION_API_KEY")
        db_id = require_env("NOTION_50_DAILY_DB_ID")
        write_to_notion(notion_api_key, db_id, date_iso, summary)
        logger.info("同期が完了しました (%s)。", date_iso)
        return 0

    except RefreshTokenExpiredError as exc:
        logger.error("%s", exc)
        return 2
    except GoogleFitSyncError as exc:
        logger.error("%s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001 - 予期せぬ例外も握りつぶさず種別を残す
        logger.error("予期せぬエラー: %s: %s", type(exc).__name__, exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
