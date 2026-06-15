#!/usr/bin/env python3
"""健康OS自動化① — Google Fit 体重 → Notion 健康ログ（週次行）自動同期。

設計方針（cloud-robust）:
- 標準ライブラリのみ（urllib）。外部依存・SDK なし。
- 認証情報はすべて環境変数から取得（リポジトリ・ログに秘匿情報を残さない）。
- 失敗時は「静かに無視」せず、stderr にエラーを出して非ゼロ終了する（受け入れ条件）。
- 同一 ISO 週に二重追記しない（冪等）。
- `--dry-run` で Notion 非書き込みの取得のみ検証ができる。

実行基盤は Render Cron / Bridge を想定（Cloud Routine は外部 API 直叩き不可の
可能性があるため。詳細は docs/health-os-automation-1.md）。本スクリプトは
実 Render 設定・トークンには一切触れない。有効化は矢嶋さん承認後に手動で行う。

必要な環境変数:
- GOOGLE_FIT_CLIENT_ID / GOOGLE_FIT_CLIENT_SECRET / GOOGLE_FIT_REFRESH_TOKEN
- NOTION_TOKEN（健康ログページにコメント/追記できるインテグレーション）
- HEALTH_LOG_PAGE_ID（既定: 37f5ae2b8d6a819784bdf8ac255dbd45）
- HEALTH_HEIGHT_CM（既定: 170）
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
DEFAULT_HEIGHT_CM = 170.0
NOTION_VERSION = "2022-06-28"
WEEK_TOKEN_PREFIX = "週次自動"


class SyncError(Exception):
    """同期処理の回復不能なエラー（呼び出し側で非ゼロ終了に変換する）。"""


# ----------------------------- 純粋ロジック ----------------------------- #

def iso_week_key(date: _dt.date) -> str:
    """ISO 年と週番号から冪等キーを作る（例: 2026-W24）。"""
    iso = date.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def compute_bmi(weight_kg: float, height_cm: float) -> float:
    """BMI を小数第1位で返す。"""
    if height_cm <= 0:
        raise SyncError("身長は正の値である必要があります")
    h_m = height_cm / 100.0
    return round(weight_kg / (h_m * h_m), 1)


def parse_googlefit_weight(aggregate_response: dict) -> float:
    """fitness.v1 dataset:aggregate のレスポンスから最新体重(kg)を取り出す。

    体重が1点も無い場合は SyncError（静かに無視しない）。
    """
    latest_value = None
    latest_end = -1
    for bucket in aggregate_response.get("bucket", []):
        for ds in bucket.get("dataset", []):
            for point in ds.get("point", []):
                end = int(point.get("endTimeNanos", 0))
                for val in point.get("value", []):
                    fp = val.get("fpVal")
                    if fp is None:
                        continue
                    if end >= latest_end:
                        latest_end = end
                        latest_value = float(fp)
    if latest_value is None:
        raise SyncError("Google Fit レスポンスに体重データが含まれていません")
    return round(latest_value, 1)


def already_synced_this_week(existing_texts: list[str], week_key: str) -> bool:
    """既存ブロックの本文に当該 ISO 週の自動追記マーカーがあれば True。"""
    token = f"{WEEK_TOKEN_PREFIX} {week_key}"
    return any(token in (t or "") for t in existing_texts)


def build_weekly_line(date: _dt.date, week_key: str, weight_kg: float,
                      height_cm: float, bmi: float) -> str:
    """健康ログページへ追記する週次行（Markdown 1行）。週キーを必ず含める（冪等用）。"""
    return (
        f"体重ログ {date.isoformat()}（{WEEK_TOKEN_PREFIX} {week_key}）: "
        f"体重 {weight_kg}kg / 身長 {int(height_cm)}cm / BMI {bmi}（Google Fit 自動同期）"
    )


def build_append_children(line: str) -> dict:
    """Notion blocks children PATCH 用ペイロード。"""
    return {
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": line}}
                    ]
                },
            }
        ]
    }


# ----------------------------- ネットワーク ----------------------------- #

def _http_json(method: str, url: str, headers: dict, payload: dict | None,
               timeout: int = 30) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        # 秘匿情報を含み得るリクエスト本文は出さない。ステータスのみ。
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:  # noqa: BLE001
            pass
        raise SyncError(f"HTTP {e.code} {method} {_safe_host(url)}: {detail}") from None
    except urllib.error.URLError as e:
        raise SyncError(f"接続失敗 {method} {_safe_host(url)}: {e.reason}") from None


def _safe_host(url: str) -> str:
    return url.split("://", 1)[-1].split("/", 1)[0]


def google_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    body = (
        f"client_id={client_id}&client_secret={client_secret}"
        f"&refresh_token={refresh_token}&grant_type=refresh_token"
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            tok = json.loads(resp.read().decode("utf-8")).get("access_token")
    except urllib.error.HTTPError as e:
        if e.code == 400:
            raise SyncError(
                "Google OAuth invalid_grant の可能性（refresh token 失効）。再認証が必要"
            ) from None
        raise SyncError(f"Google OAuth HTTP {e.code}") from None
    if not tok:
        raise SyncError("access_token を取得できませんでした")
    return tok


def fetch_latest_weight(access_token: str, days: int = 30) -> float:
    now = _dt.datetime.now(_dt.timezone.utc)
    start_ms = int((now - _dt.timedelta(days=days)).timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)
    payload = {
        "aggregateBy": [{"dataTypeName": "com.google.weight"}],
        "bucketByTime": {"durationMillis": end_ms - start_ms},
        "startTimeMillis": start_ms,
        "endTimeMillis": end_ms,
    }
    resp = _http_json(
        "POST",
        "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate",
        {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        payload,
    )
    return parse_googlefit_weight(resp)


def fetch_page_block_texts(notion_token: str, page_id: str) -> list[str]:
    texts: list[str] = []
    cursor = None
    while True:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        resp = _http_json(
            "GET", url,
            {"Authorization": f"Bearer {notion_token}",
             "Notion-Version": NOTION_VERSION},
            None,
        )
        for block in resp.get("results", []):
            btype = block.get("type")
            rich = (block.get(btype) or {}).get("rich_text", []) if btype else []
            texts.append("".join(r.get("plain_text", "") for r in rich))
        if resp.get("has_more"):
            cursor = resp.get("next_cursor")
        else:
            break
    return texts


def append_weekly_line(notion_token: str, page_id: str, line: str) -> None:
    _http_json(
        "PATCH",
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        {"Authorization": f"Bearer {notion_token}",
         "Notion-Version": NOTION_VERSION,
         "Content-Type": "application/json"},
        build_append_children(line),
    )


# -------------------------------- main -------------------------------- #

def run(dry_run: bool = False, today: _dt.date | None = None) -> int:
    today = today or _dt.datetime.now(_dt.timezone.utc).date()
    week_key = iso_week_key(today)
    height_cm = float(os.environ.get("HEALTH_HEIGHT_CM", DEFAULT_HEIGHT_CM))
    page_id = os.environ.get("HEALTH_LOG_PAGE_ID", DEFAULT_HEALTH_LOG_PAGE_ID)

    cid = os.environ.get("GOOGLE_FIT_CLIENT_ID")
    csecret = os.environ.get("GOOGLE_FIT_CLIENT_SECRET")
    rtoken = os.environ.get("GOOGLE_FIT_REFRESH_TOKEN")
    ntoken = os.environ.get("NOTION_TOKEN")
    if not all([cid, csecret, rtoken, ntoken]):
        raise SyncError(
            "必須の環境変数が未設定です（GOOGLE_FIT_* / NOTION_TOKEN）"
        )

    access = google_access_token(cid, csecret, rtoken)
    weight = fetch_latest_weight(access)
    bmi = compute_bmi(weight, height_cm)
    line = build_weekly_line(today, week_key, weight, height_cm, bmi)

    existing = fetch_page_block_texts(ntoken, page_id)
    if already_synced_this_week(existing, week_key):
        print(f"[skip] {week_key} は同期済みです")
        return 0

    if dry_run:
        print(f"[dry-run] 追記予定: {line}")
        return 0

    append_weekly_line(ntoken, page_id, line)
    print(f"[ok] 追記しました: {line}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Google Fit 体重 → Notion 健康ログ 同期")
    parser.add_argument("--dry-run", action="store_true",
                        help="Notion へ書き込まず取得のみ検証する")
    args = parser.parse_args(argv)
    try:
        return run(dry_run=args.dry_run)
    except SyncError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
