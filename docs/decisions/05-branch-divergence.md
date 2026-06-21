# 決定パッケージ ⑤: ブランチ分岐の解消（canonical ブランチ確定）

> ④⑥より先に読む。④（体重ゼロ化）は本件に依存する。

## 1. 決める問い（1つ）
分岐した複数ブランチのうち、**どれを唯一の正本（canonical / deploy）ブランチにするか**。そして他系統の固有資産をそこへ集約するか。

## 2. 結論ファースト（推奨）
**A. 本番系 `claude/notion-api-setup-BQGwN` を canonical と確定**し、`origin/main` 側の固有資産（`health/`＝体重同期・週次リマインダー、`dashboard` 系の差分があれば）を**本番系へ前方移植**する。`master` は deploy 候補から退役。

## 3. 現状の事実（検証済み）
- `origin/main` と本番系 `claude/notion-api-setup-BQGwN` の**共通祖先は初期コミット `695c40a` のみ**＝ほぼ完全に分岐した別系統。
- `consensus.py` 行数: 本番系 **649** / `master` **446** / `origin/main` **0（存在しない）**。
  → `origin/main` は consensus を持たない「health/dashboard 系」、本番系は「consensus/bridge 系」。
- `origin/main` 固有: `health/weight_sync.py`・`health/weekly_review_reminder.py`・`tests/test_weight_sync.py`・`docs/health-os-automation-1.md`・`weight-log.html`。
- Render の deploy 元は本番系（`render.yaml`: `startCommand: python main.py`）。`origin/main` を誤って deploy 元にすると consensus が動かない。
- 本番系の CI は branch-scoped。`origin/main` は別 CI 系統（監査 High「CI 分岐」）。

## 4. 選択肢（メリット / デメリット）
| 選択肢 | メリット | デメリット |
|---|---|---|
| **A.（推奨）本番系を canonical 化＋health/ を前方移植** | deploy 元が1本に定まる／体重同期(④)の置き場が確定／監査の「正本不在」High を解消 | 移植 PR が必要（health/ は consensus 非依存なので影響は限定的） |
| B. `origin/main` を canonical 化 | health/dashboard が揃っている | consensus/bridge 系一式の移植が必要で重い・Render 再設定リスク大 |
| C. 今はやらない | 作業ゼロ | 「どれが本番か」曖昧なまま。④が前に進めず、誤 deploy リスクが残る |

## 5. リスクと前提・依存
- リスク: 移植時の取りこぼし／CI 系統の二重管理。→ 移植は health/（自己完結）から小さく始めれば低リスク。
- 前提・依存: なし（本件が ④ の前提）。

## 6. 必要な人間 / インフラ作業
- **どのブランチを正本にするかの戦略判断**（矢嶋さん）。
- 確定後の移植 PR 作成はエージェントが代行可（本番基点・PR まで）。Render deploy 元の確認は人間。

## 7. 影響範囲
- Render 設定変更: 確定の確認のみ（変更は伴わない想定） / Notion スキーマ変更: なし / 本番挙動変更: なし（移植時点では） / 新規 Cloud Routine: なし

## 8. ロールバック手順
- 移植は PR 単位。問題があれば該当 PR を revert すれば元の本番系に戻る（deploy 元は不変）。

## 9. Go したら最初の一手
- 「A で確定」をいただければ、まず **`health/` 一式（weight_sync / weekly_review_reminder / test）を本番系へ前方移植する PR** を作成（consensus 非依存＝低リスク）。これが ④ の置き場になる。
