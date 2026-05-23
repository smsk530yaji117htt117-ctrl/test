# Router Rules: Meeting Result Classification

## 文書の位置づけ

この文書は Router v1 の実装ではない。AI Consensus Log の Complete 済み会議結果を Handoff v2 へ渡すか、人間判断へ戻すかを決めるための判断基準である。今回はルールを文書化し、`meeting_result_processor.py` の最小分類に利用するだけで、自動ルーティングや自動開発は行わない。

## 判定順序

判定は、実行可能性と安全性を分けて扱う。

1. `Status` が `Complete` であることを確認する。Complete 以外は処理を進めない。
2. コード変更やスクリプト作成など、具体的な開発作業が存在するかを見る。
3. 同じ結果に保護対象、承認要求、権限判断が含まれるかを見る。
4. 開発作業が無ければ、調査、人間判断、または action 無しのどれが主目的かを見る。

## 分類基準

| Classification | 判定基準 | 例 |
| --- | --- | --- |
| `dev_task` | コード変更、スクリプト作成、テスト、Handoff/relay 生成、具体的な実装依頼へ落とせる | Router の関数を実装する、分類スクリプトを追加する |
| `research_task` | 調査、比較、設計検討、情報収集が中心で、直ちにコード変更へ進めない | 複数方式を比較して報告する |
| `human_review` | 人間承認、費用、権限、リスク、安全性の判断が主目的で、実装タスクが確定していない | Notion フィールド追加を採用するか承認する |
| `no_action` | 対応済み、明確な次アクション無し、雑談、記録、参考情報のみ | 完了報告を記録するだけ |

## human_review_required の優先条件

`human_review_required` は `classification` を上書きする分類ではなく、作業開始を止める安全ゲートである。

次の場合、具体的な開発タスクが存在するなら `classification = dev_task`、かつ `human_review_required = true` とする。

- 実装候補に Notion スキーマ変更、DB フィールド追加、`attempt_count`、`fallback_triggered` が関係する。
- コード変更候補に `.env`、API キー、token、secret の表示または変更が関係する。
- Render 設定、本番削除、Billing、GitHub Settings / Secrets / Actions が関係する。
- `git push`、PR merge、PR 自動マージが関係する。
- Router または自動実行に関わり、権限・安全性について明示的な判断が必要である。

一方、保護対象の採否判断しか示されず、実装の範囲や受入条件が不足している場合は `classification = human_review` とする。人間が承認して安全な実装範囲を定義するまで Handoff の実行可能チケットにしない。

## 自動実行してはいけない条件

以下を含む結果は、Handoff を生成できても次 AI が自動実行してはいけない。必ず人間確認に戻す。

- Notion スキーマ変更、AI Consensus Log または AI Handoff DB のプロパティ追加・型変更
- `.env`、API キー、token、credentials、secret の表示・編集・移動
- Render 設定、デプロイ設定、本番データまたは本番ページの削除
- Billing、GitHub Settings、GitHub Secrets、GitHub Actions 設定の変更
- `git push`、PR merge、PR 自動マージ
- Target Files 外の編集
- 作業ディレクトリ、source of truth、受入条件、復旧方法が不明な作業

## 禁止事項

- PR 自動マージは禁止する。
- Notion スキーマ変更は禁止する。必要に見えても実行せず、人間承認の対象として記録する。
- `.env` / API キー / Render / Billing / GitHub Settings / Secrets / Actions は人間確認へ戻す。
- 本 MVP は Request Inbox、Router v1 本実装、自動開発、JSONL Event Store 全面移行を実装しない。

## Handoff v2への接続方針

Claude が停止した場合や、Codex / Antigravity / GPT へ作業を渡す場合は、分類結果を直接自動実行命令にせず Handoff v2 の作業チケットへ変換する。

Handoff v2 は最低限次を先に明記する。

- 正しい Repository と Working Directory
- Target Files と Execution Environment
- Git Managed の状態
- Do Not Touch と Escalation Rule
- Acceptance Criteria と `Human Review Required`

既存 relay はこの安全情報を `Notes` 内の `Critical Scope Information` として AI Handoff DB に保存し、次 AI Prompt の先頭へ表示できる。追加フィールドを Notion に作らずに安全な引継ぎを行う。

## 今回の実ページ判断

Page ID `3635ae2b-8d6a-81d6-bb2d-f806f8d6e4f8` は、Router v1 / `select_ai` / fallback prompt の実装候補を含むため `dev_task` 候補である。同時に `attempt_count` / `fallback_triggered` のフィールド追加案は Notion スキーマ変更に触れる可能性があるため、判定は次のとおりとする。

```text
classification = dev_task
human_review_required = true
```

生成した Handoff は登録・Prompt 生成の接続確認に使用できるが、保護対象の変更や自動実行の許可を意味しない。
