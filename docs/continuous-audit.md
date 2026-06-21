# 継続監査（しくみ1）: 変更検知 → 監査差分追記

改善エンジンの「燃料の自動補充」。最後の監査以降に変わったコードから、監査項目を
**自動で再生成し続ける**ための仕組みと、既存 Dispatcher への組み込み仕様。
本書は仕様確定（docs）まで。**実ルーチン化・新規 Cloud Routine・スケジュール変更は人間承認後**。

## 部品
- `tools/audit_scan.py` — 決定論的な静的スキャナ（LLM不要）。既知の負債パターンを検出する。
  - 検出ルール: urlopen-timeout(High) / env-subscript(Med) / todo-marker(Low) / untested-module(Med) / dead-func(Low)。
  - 差分モード `--since <ref>`: 変更ファイルだけを内容監査（横断ルールは整合のため全体評価）。
  - 出力: Markdown（既存 `research/code_audit.md` と同じ表形式）/ JSON。
- `research/code_audit.md` — baseline（多エージェント read-only 監査の確定版）。在庫の起点。

## 在庫の数え方（着手前チェック）
1. `python tools/audit_scan.py --format json` で現在の検出数（severity 別）を得る。
2. `research/code_audit.md` の未消化（未PR化）項目数と突き合わせる。
3. 在庫が薄い（例: High 0 / Med 少数）なら、実装より先に本スキャナで燃料を補充する。

## Dispatcher への組み込み仕様（変更検知 → 監査差分追記）
> 実装はせず、Dispatcher（Cloud Routine、プロンプトはクラウド保管）に追記する手順を定義する。
> ルーチン化・スケジュール変更は人間承認後。

想定フロー（承認後にプロンプトへ反映）:
1. **変更検知**: Dispatcher 実行時、本番ブランチ `claude/notion-api-setup-BQGwN` の前回監査 SHA を Notion（後述の保管先）から読み、`HEAD` との差分があるか判定。差分なければ早期終了（`routines/skip-empty-routine.md` のガードと整合）。
2. **差分監査**: `python tools/audit_scan.py --since <前回SHA> --format markdown` を実行。
3. **監査差分追記**: 出力を「監査在庫」ページ（Notion 既存ページ。**新規DB・スキーマ変更はしない**）または `research/code_audit.md` への追記 PR として起票。新規 code-only 項目は AI Handoff DB に Draft 起票（重複チェック必須＝Notion 制約リスト 2026-06-15 の学び）。
4. **前回監査 SHA を更新**。

### 保管先の選択（承認時に確定）
- 案1: 既存の軽量 Notion ページに追記（スキーマ変更なし）。
- 案2: `research/` 配下の Markdown を PR で更新（コードと同じ流れ・人間レビュー可）。← docs 整合性の点で推奨。

## CI への任意組み込み（将来・別判断）
`audit_scan.py --since origin/<base> --fail-on high` を PR の情報提供ジョブとして追加すると、
新規 High 負債の混入を可視化できる（ゲート化＝必須チェックにするかは別途人間判断）。

## 制約遵守
- 新規 Cloud Routine / スケジュール変更 / Render 設定 / Notion スキーマ変更はしない（本書は仕様まで）。
- スキャナは**読み取り専用**。コードや Notion を書き換えない。
