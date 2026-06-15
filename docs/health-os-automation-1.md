# 健康OS自動化① — Google Fit 体重 → Notion 自動同期 ＋ 週次レビューのリマインダー

関連 Handoff: <https://app.notion.com/p/3805ae2b8d6a817d9c2bf837c8df4045>
健康ログ（正本ページ）: <https://app.notion.com/p/37f5ae2b8d6a819784bdf8ac255dbd45>

## 目的（Goal）

健康OS（顔・上半身ログ）の手作業を2つ削減する。

1. **体重同期**: 直近の Google Fit 体重を、人手なしで Notion 健康ログ（週次行）へ反映する。
2. **週次リマインダー**: 毎週日曜 21:00 JST に Notion コメント（ユーザーメンション）で「最新写真を貼ってレビュー」を促す。

## 成果物（このPRに含まれるもの）

| ファイル | 役割 |
|---|---|
| `health/weight_sync.py` | Google Fit 体重 → Notion 健康ログ 週次追記（cloud-robust・stdlib のみ） |
| `health/weekly_review_reminder.py` | 日曜21:00 JST の週次レビュー リマインダー投稿 |
| `tests/test_weight_sync.py` | 体重同期の純粋ロジック ユニットテスト（ネットワーク非依存） |
| `tests/test_weekly_review_reminder.py` | リマインダーの純粋ロジック ユニットテスト |
| `docs/health-os-automation-1.md` | 本書（設計・有効化手順） |

`python3 -m unittest discover -s tests` → **17 passed / 0 failed**。

## 設計上の判断（cloud-robust 方式）

- Handoff の Risks に「Cloud Routine は外部 API 直叩き不可の可能性 → Render 橋の検討」とある。
  既存 `personal-os-consensus`（Render Cron）や PR #13 の `google_fit_sync.py` と同じく、
  **Render Cron / Bridge を実行基盤に想定**する。本スクリプトは外部依存を持たず
  （標準ライブラリのみ）、認証情報はすべて環境変数から読む。
- **失敗時は静かに無視しない**: いずれのスクリプトもエラー時に stderr へ出力し
  非ゼロ終了する（受け入れ条件）。`invalid_grant`（refresh token 失効）は専用メッセージで判別。
- **冪等**: 体重同期は ISO 週キー（例 `2026-W25`）を追記行に埋め込み、同一週の二重追記を防ぐ。
- **秘匿情報を残さない**: トークン・シークレットはログ・PR・コミットに出さない。HTTP エラーは
  ホスト名とステータスのみ記録する。

## 既存資産との関係（重複回避）

- PR #13（`google_fit_sync.py`）は別タスク（token 失効修復・50_Daily 日次同期）。
  本 PR は **健康ログページの週次行**を対象にしており目的・書き込み先が異なる。
- 将来的に Google Fit 取得部を共通化する余地がある（フォローアップ候補）。本 PR では
  既存ファイルを変更せず、独立したスクリプトとして追加するに留める。

## 必要な環境変数（有効化時に Render 側で設定）

| 変数 | 用途 |
|---|---|
| `GOOGLE_FIT_CLIENT_ID` / `GOOGLE_FIT_CLIENT_SECRET` / `GOOGLE_FIT_REFRESH_TOKEN` | Google Fit OAuth |
| `NOTION_TOKEN` | 健康ログページへ追記/コメントできるインテグレーション |
| `HEALTH_LOG_PAGE_ID` | 既定 `37f5ae2b8d6a819784bdf8ac255dbd45` |
| `HEALTH_HEIGHT_CM` | 既定 `170` |
| `REVIEW_MENTION_USER_ID` | 既定 矢嶋勇輝 `173d872b-594c-81b4-af4a-000262688c71` |

## 動作確認（ローカル / dry-run）

```bash
python3 -m unittest discover -s tests        # ロジックの自動テスト
python3 -m health.weight_sync --dry-run      # 取得のみ（env 設定後・Notion 非書き込み）
python3 -m health.weekly_review_reminder --dry-run --force
```

## ⚠️ 有効化に必要な手動操作（矢嶋さん承認後 / Claude Code 単独では不可）

本 PR は**コードと手順の追加のみ**で、Render 設定・トークン・Notion スキーマ・本番スケジュールには
一切変更を加えていない。実稼働には以下が必要（順序）:

1. Google OAuth 同意画面を「本番（In production）」に公開（refresh token 7日失効の恒久対策）。
2. ローカルで refresh token を取得し、Render 環境変数に投入（`NOTION_TOKEN` 含む）。
3. `python3 -m health.weight_sync --dry-run` で HTTP 200 と体重取得を確認。
4. 週次スケジュールを設定:
   - 体重同期: 週1（例 月曜朝）に `health/weight_sync.py` を実行。
   - リマインダー: **日曜 21:00 JST** に `health/weekly_review_reminder.py` を実行
     （cron は UTC のため `0 12 * * 0`）。
5. 初回稼働を観察し、健康ログへ週次行が入ること・リマインダーが届くことを確認。

> マージ・Routine 有効化は矢嶋さんの明示承認後に行うこと（自動マージ禁止）。
