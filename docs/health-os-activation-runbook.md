# 健康OS自動化①（体重ゼロ化）有効化ランブック

④「体重の手入力ゼロ化」を有効にするための、**人間が行うクリック順手順**。
コード（`health/weight_sync.py`）は本番に移植済み（PR #40）。残るのは OAuth 発行・Notion 接続・
Render 設定という**インフラ作業**で、エージェントは代行できない。本書はその順番・必要値・検証・
ロールバックを1枚にまとめたもの。判断材料は [decisions/04-weight-zero-input.md](decisions/04-weight-zero-input.md)。

> このランブックは設定値の一覧と手順のみ。**実際のキー・トークンはここに書かない**（Render の
> 環境変数に直接入れる）。`.env` をリポジトリに置かない。

## 0. 前提
- `weight_sync.py` がやること: Google Fit から直近の体重を取得 → BMI 算出（身長 `HEALTH_HEIGHT_CM` 既定170）→ Notion 健康ログページに「週次行」を追記。**同一 ISO 週には二重追記しない（冪等）**。`--dry-run` で取得のみ検証可。
- 使う API: Google OAuth2 トークン更新（`oauth2.googleapis.com/token`）＋ Google Fit REST（`fitness/v1/users/me/dataset:aggregate`, `com.google.weight`）。
- ⚠️ **要確認（未確認）**: Google は Fit REST API の段階的終了を告知している。対象アカウントで体重データが取得できるか、まず `--dry-run` で実地確認する（Web 情報だけでは判断しない＝制約準拠）。取得不可なら別データ源（Health Connect 等）の検討が必要。

## 1. 必要な環境変数（Render に設定）
| 変数 | 必須 | 既定 | 中身 |
|---|---|---|---|
| `GOOGLE_FIT_CLIENT_ID` | ✔ | — | OAuth クライアント ID |
| `GOOGLE_FIT_CLIENT_SECRET` | ✔ | — | OAuth クライアントシークレット |
| `GOOGLE_FIT_REFRESH_TOKEN` | ✔ | — | 手順2で取得するリフレッシュトークン |
| `NOTION_TOKEN` | ✔ | （consensus と同じ統合）| Notion 統合トークン |
| `HEALTH_LOG_PAGE_ID` | 任意 | `37f5ae2b8d6a819784bdf8ac255dbd45` | 健康ログページ |
| `HEALTH_HEIGHT_CM` | 任意 | `170` | 身長(cm) |

## 2. Google OAuth の発行（クリック順）
1. **Google Cloud Console** → プロジェクトを作成 or 選択。
2. 「API とサービス」→ **ライブラリ** → **Fitness API** を有効化。
3. **OAuth 同意画面** → ユーザータイプ **External** → アプリ名等を入力 → **テストユーザー**に矢嶋さんの Google アカウントを追加（公開審査を避け Testing のまま運用可）。
4. **スコープ**に `https://www.googleapis.com/auth/fitness.body.read` を追加。
5. 「認証情報」→ **OAuth クライアント ID を作成** → タイプは **デスクトップアプリ**（リフレッシュトークンを手作業で取りやすい）。→ `client_id` と `client_secret` を控える（= 変数1,2）。
6. **リフレッシュトークンの取得**（どちらか）:
   - 簡易: OAuth 2.0 Playground で自分の client を使い、scope `fitness.body.read` を承認 → `refresh_token` を取得。
   - or ローカルで一度だけ認可フローを回して `refresh_token` を取得。
   - 取得した値を `GOOGLE_FIT_REFRESH_TOKEN`（= 変数3）に。
   - 注: `access_type=offline` ＋ 初回同意でないと refresh token が出ないことがある。出ない場合は同意済みアプリのアクセスを一度解除して再認可。
7. ⚠️ Testing 状態の refresh token は**期限切れ（約7日／invalid_grant）**になりうる。本運用前に「公開（In production）」へ昇格させるか、失効時の再取得手順を決めておく。コードは `invalid_grant` を検知して明示エラーを出す。

## 3. Notion 接続
- 健康ログページ `HEALTH_LOG_PAGE_ID`（既定 `37f5ae2b…`）に、`NOTION_TOKEN` の統合を**接続（Connections に追加）**する。
  - 新設ページは統合にデフォルト未共有（制約リストの既知事項）。**追記できる権限**が要る。

## 4. Render 設定（既存 consensus cron には触れない）
- 上記 env を Render に登録。
- `weight_sync.py` を回す**新規 Cron Job**を用意（例: 週1・日曜朝）。コマンドは `python health/weight_sync.py`。
  - ⚠️ 既存の `personal-os-consensus`（10分 cron, `python main.py`）は**変更しない**。体重同期は別サービス/別ジョブとして分離する（Render は cron と web の同居不可と同じ思想で、役割ごとに分ける）。
  - Cloud Routine は使わない（外部 API 直叩きブロックのため。`weight_sync` のコメントどおり Render 実行が前提）。

## 5. 検証（有効化の前に必ず）
```bash
# Render の env を入れた環境で（または手元に同じ env を用意して）
python health/weight_sync.py --dry-run
```
- 期待: 体重取得 → BMI 算出 → 追記予定行が表示され、**Notion へは書かない**。
- 失敗パターンと意味:
  - `invalid_grant` → refresh token 失効（手順2-7）。
  - `HTTP 4xx fitness…` → スコープ不足／Fit にデータ無し／API 終了の影響（要確認項目）。
  - `必須の環境変数が未設定` → 変数1〜4 の不足。
- dry-run が通ったら、Cron を有効化して本運用へ。

## 6. ロールバック
- Cron Job を停止すれば同期は止まる。env を外せば完全停止。コードは「読み取り→週次行を追記（冪等）」のみで、停止しても既存データは壊れない。

## 7. 完了の定義（DNA: 手入力ゼロ）
- 毎週、体重が**手入力ゼロ**で健康ログに記録される。矢嶋さんの操作は不要。
- 失効・取得不可時はコードが明示エラーで止まる（無言で壊れない設計）ので、気づける。
