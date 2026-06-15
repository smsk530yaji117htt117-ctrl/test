# HUMAN_REVIEW_REQUIRED_POLICY — 人間レビュー要否ポリシー

PersonalOS 1.3-β。会議（AI合議）→ Handoff 自動接続において、
`human_review_required`（true/false）をどう判定し、起票・実行へどう反映するかを定義する。

## 原則

> **可逆なら自動・不可逆なら人間承認。**

- 起票（Handoff DB への行追加）は**常に自動でよい**。
- gate（止める場所）は**実行側**＝ executor 投入・PR merge・デプロイのタイミング。

## `true` を立てる不可逆リスト（不可逆・高リスク）

以下に該当するものは `human_review_required = true`。

- 投資OS の発注・取引
- 送金 / 外部送信（メール・API 経由の外部通知含む）
- 本番 merge・デプロイ
- destructive な DB 操作（削除・上書き）
- スキーマ変更・migration
- 認証・権限の変更
- Render 設定の変更

## エスカレータ（可逆でも `true`）

可逆な操作でも、以下のいずれかに該当する場合は `true` に引き上げる。

- `confidence < 閾値`（自信度が低い）
- `novelty`（前例がない・初めてのパターン）
- `budget 超過`（コスト上限を超える）

## 反映ルール

| human_review_required | 起票 | Status | executor |
|---|---|---|---|
| `true` | する（自動） | `Draft`（保留） | **投入しない**（人間承認後） |
| `false` | する（自動） | `Ready` | 投入可 |

- `true` → `Status=Draft` で保留。または `Ready` で起票し、実装後に **PR で人間承認**。
- 曖昧・未記載の場合は**安全側に倒して `true`**（`meeting_result_processor.DEFAULT_HUMAN_REVIEW_REQUIRED`）。
- **初回実装は `human_review_required=true` を維持**する（自動接続の挙動を人間が確認するまで）。

## 実装メモ

- 判定値の解析: `meeting_result_processor.parse_synthesis()` の `human_review_required`
- Status への反映: `relay/generate_handoff_prompt._status_for()`（true→Draft / false→Ready）
- executor 投入は本リレー層では一切行わない（起票のみ）。実行 gate は別系統。
