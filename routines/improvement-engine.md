# 改善エンジン・ワークフロー定義（PersonalOS 完成度引き上げ）

PersonalOS の「改良が継続的に湧き、矢嶋さんには"判断"だけが届く」状態を回すための
ワークフロー定義。1回の実行＝「探索→ギャップ→優先度→実装(PR作成まで)→報告」を回す。
このファイルは**ワークフロー実行エージェントが冒頭で読む手順書**であり、実行ルーチンそのもの
（Cloud Routine）ではない。ルーチン化・スケジュール化は人間承認後。

## コアDNA（ものさし）
手動入力・意志力・感情労働をゼロに近づけ、判断を外部システムに委ねる。
「まだ手で入力／意志力依存／壊れやすい／自動化が途切れる」箇所を完成度の負債として最優先で拾う。

## Phase 0 — 起動時に必ず読む（順番厳守）
1. **[lessons-learned.md](lessons-learned.md)** — 過去の詰まり・失敗・段取り。L-001（マージは未マージ前提）を特に厳守。
2. Notion 引き継ぎ書 `36a5ae2b8d6a8145bb04d0f357e5acc5` と セッションログ直近3件 `36b5ae2b8d6a816e8ddbd12adbaf699b`。
3. Notion「🚧 Cloud Routine 制約リスト」`36a5ae2b8d6a81c3809fdb31dd9c2c5d`（環境制約の正本）。
4. **オープンPRの事実確認**: `git fetch origin` ＋ GitHub PR API で本番ブランチ `claude/notion-api-setup-BQGwN` の head と各PRの `merged` を確認（L-001）。

## Phase 1 — 燃料の確認（着手前、L-002）
- `research/code_audit.md`（baseline 監査）と `tools/audit_scan.py` の出力で**未消化の負債在庫**を数える。
- 在庫が薄い → 実装より先に「しくみ1（継続監査）」で燃料を補充する。

## Phase 2 — 仕分け（消す負債の種類で分類）
各候補を次の軸で仕分ける:
- **コードだけで完結し、PR作成まで自分で終えられるか**（YES＝自走対象）。
- 人間判断・インフラ・スキーマ・Render・新規Cloud Routine・スケジュール変更を伴うか（YES＝ハードストップ。決定パッケージ化して届ける＝しくみ3）。

## Phase 3 — 自走（価値の高い順に連続PR）
- 本番基点 `claude/notion-api-setup-BQGwN` から**個別ブランチ**を切る（スタックしない）。
- ローカルで `python -m pytest` を green にしてから push（CI相当）。
- PR base は必ず `claude/notion-api-setup-BQGwN`。`gh` 不在なら GitHub API で PR 作成。
- 各PRを「PR番号 / CI結果 / 強化したしくみ or 消したDNA負債」で1行報告。
- code-only の在庫が尽きたら**無理に作らず**、残りを決定パッケージ化して停止報告。

## 必ず止まって報告（ハードストップ）
- マージ（人間承認必須。エージェントは PR 作成まで）。
- 新規 Cloud Routine・スケジュール変更・Render 設定・Notion スキーマ変更。
- ④体重ゼロ化 / ⑤ブランチ分岐解消 / ⑥meeting routing live化 そのものの実行（戦略・インフラ判断）。

## 絶対制約
- Notion スキーマ変更しない / `.env`・APIキー・トークンを表示しない / Render 設定変更しない / `consensus.py` を止めない。
- PR 自動マージ禁止 / main 直 push 禁止。
- Cloud Routines は許可リスト方式・15回/日上限。公式コネクタ（Slack/Linear/Google Drive/GitHub）以外への直接 HTTP はブロック前提。

## 報告フォーマット（相手＝矢嶋さん）
敬語ベース・結論ファースト・スマホ2画面以内・選択肢は表（項目/メリット/デメリット）＋推奨・確認事項は1つに絞る。

## 終了時
- 大きな進捗はセッションログ先頭に追記（**事実確認済みの範囲のみ**）。
- 新しい詰まり・失敗・段取りは [lessons-learned.md](lessons-learned.md) に追記してから終わる。
