# 決定パッケージ ④: 体重の手入力ゼロ化（健康OS自動化①の有効化）

> 純粋に「手入力を消す」最高の DNA 勝ち。ただし ⑤（ブランチ分岐解消）と OAuth/Render 設定が前提。

## 1. 決める問い（1つ）
体重の週次手入力を撤廃し、**Google Fit → Notion 健康ログへの自動同期を有効化**するか。有効化するなら実行基盤は Render Cron / Bridge でよいか。

## 2. 結論ファースト（推奨）
**A. 有効化する。** 同期コード `health/weight_sync.py` は完成済み（stdlib のみ・冪等・`--dry-run` 付き・失敗時非ゼロ終了）で、残るのは **OAuth 資格情報の発行と Render への設定**という人間・インフラ作業のみ。コアDNA「手入力ゼロ」に最も直接効く。ただし⑤を先に確定。

## 3. 現状の事実（検証済み）
- コードは `origin/main` に存在: `health/weight_sync.py` / `health/weekly_review_reminder.py` / `tests/test_weight_sync.py` / `docs/health-os-automation-1.md`。**本番系には未取り込み**（＝⑤に依存）。
- 設計: 標準ライブラリのみ・認証は全て env・同一 ISO 週に二重追記しない冪等・`--dry-run` で取得のみ検証可。実行基盤は **Render Cron / Bridge を想定**（Cloud Routine は外部API直叩き不可のため）。
- 必要 env: `GOOGLE_FIT_CLIENT_ID` / `GOOGLE_FIT_CLIENT_SECRET` / `GOOGLE_FIT_REFRESH_TOKEN` / `NOTION_TOKEN`（既存）/ `HEALTH_LOG_PAGE_ID`（既定 `37f5ae2b8d6a819784bdf8ac255dbd45`）/ `HEALTH_HEIGHT_CM`（既定170）。
- 現状の体重記録は「週次の手申告」（引き継ぎ書）。

## 4. 選択肢（メリット / デメリット）
| 選択肢 | メリット | デメリット |
|---|---|---|
| **A.（推奨）有効化（Render Cron/Bridge）** | 週次の手入力が消える（純DNA勝ち）／コードは完成・冪等・dry-run検証可 | OAuth 発行と Render env 設定が必要（人間・インフラ）／⑤が前提 |
| B. Cloud Routine で実行 | 既存の自動化基盤に乗る | **外部 API 直叩きブロック**で Google Fit 取得不可の公算大（制約リスト）。非推奨 |
| C. 今はやらない | 作業ゼロ | 体重の手入力・意志力依存が残る |

## 5. リスクと前提・依存
- 前提・依存: **⑤の確定**（health/ の置き場）→ Google OAuth 設定 → Render env/スケジュール。
- リスク: OAuth リフレッシュトークンの失効（要更新運用）。dry-run で取得検証してから本番投入すれば書込みリスクは低い。

## 6. 必要な人間 / インフラ作業（エージェント代行不可）
1. **Google 側**: Cloud プロジェクトで Fitness API 有効化 → OAuth 同意画面（外部なら検証）→ リフレッシュトークン取得。←「OAuth 公開」作業。
2. **Render 側**: 上記 env を設定 ＋ `weight_sync.py` を回す cron スケジュール/サービスを用意。
3. **Notion**: 健康ログページ `HEALTH_LOG_PAGE_ID` に当該インテグレーションを接続。
- エージェント代行可: ⑤確定後の health/ 移植 PR、`--dry-run` 検証手順の整備、ドキュメント化。

## 7. 影響範囲
- Render 設定変更: **あり（env＋スケジュール）** / Notion スキーマ変更: なし（既存ページに追記） / 本番挙動変更: 健康ログへの週次自動追記が始まる / 新規 Cloud Routine: なし（Render で実行）

## 8. ロールバック手順
- Render のスケジュールを停止すれば同期は止まる（コードは読み取り→追記のみ、冪等なので重複書込みなし）。env を外せば完全停止。

## 9. Go したら最初の一手
- ⑤を A で確定後、**health/ 一式を本番系へ移植する PR** を作成（エージェント）。並行して矢嶋さんが Google OAuth 資格情報を発行 → 揃ったら `python health/weight_sync.py --dry-run` で取得検証 → 問題なければ Render スケジュール有効化。
