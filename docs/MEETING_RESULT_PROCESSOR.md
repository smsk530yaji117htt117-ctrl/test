# Meeting Result Processor MVP

## 目的

`Meeting Result Processor` は、AI Consensus Log の `Status: Complete` となった会議結果を、次の安全な作業導線へ変換する最小実装である。

1. 会議結果を `dev_task` / `research_task` / `human_review` / `no_action` に分類する。
2. `dev_task` であれば Handoff v2 Markdown を生成する。
3. 人間が内容を確認した後、既存の `relay/create_handoff_page.py` で AI Handoff DB に登録できる。
4. 既存の `relay/generate_handoff_prompt.py` で次 AI 用 Prompt を生成できる。

本 MVP は完全自動開発ではなく、人間承認つきの半自動導線である。

## 入力と出力

入力は AI Consensus Log の Complete 済み Notion page ID である。Processor はページの `Question`、`Status`、`Synthesis`、既存の AI response プロパティを読み取るが、元ページを更新しない。`Status` が明示的に `Complete` でないページは `no_action` として扱い、Handoff を生成しない。

出力は次の三つである。

- `classification`: `dev_task` / `research_task` / `human_review` / `no_action`
- `human_review_required`: 保護対象または明示承認条件を含む場合の安全フラグ
- `Handoff v2 Markdown`: `classification = dev_task` の場合のみ生成する relay 互換ドラフト

## 4分類

| Classification | 意味 | Handoff生成 |
| --- | --- | --- |
| `dev_task` | コード変更、スクリプト作成、テスト、relay/Handoff 生成など、実装タスクへ落とせる結果 | 生成する |
| `research_task` | 調査、比較、設計検討、情報収集が中心で、まだコード変更へ進めない結果 | 生成しない |
| `human_review` | 人間の承認、権限、費用、安全性などの判断が主タスクである結果 | 生成しない |
| `no_action` | 完了済み、次アクションなし、記録・参考情報のみ、または actionable な依頼を判定できない結果 | 生成しない |

## human_review_required

`human_review_required` は分類とは別の安全フラグである。実装候補が明確でも、次のいずれかが含まれれば `classification = dev_task` のまま `human_review_required = true` とする。

- Notion スキーマ、DB フィールド追加、`attempt_count`、`fallback_triggered`
- `.env`、API キー、secret
- Render 設定、本番削除
- GitHub Settings / Secrets / Actions、Billing
- `git push`、PR merge、PR 自動マージ
- 完全自動または自動実行に関する安全判断
- 明示的な人間承認要求

実装タスクが存在せず、上記の判断そのものが主目的であれば `classification = human_review` とする。詳細な優先順位は `docs/router_rules.md` に定義する。

## Handoff v2生成方針

Processor の Markdown は `docs/HANDOFF_STANDARD_V2.md` の安全項目を含みつつ、既存の `relay/create_handoff_page.py` が読める `Field:` ラベル形式で生成する。これにより relay の変更や Notion スキーマ変更を行わない。

生成される Handoff は処理対象の会議結果と分類結果に基づく `Draft` であり、具体的な編集対象ファイルは実装開始前に確認する。会議本文は `Raw Log` に転載せず、トレース用の page ID、マスク済み title、status と安全注記だけを出力する。title など出力に残る文字列でも、API key や token に見える値は `[REDACTED]` に置換する。

含める項目:

- `Task`, `Status`, `Repository`, `Working Directory`, `Target Files`
- `Execution Environment`, `Git Managed`, `Do Not Touch`
- `Goal`, `Current State`, `Next Action`, `Acceptance Criteria`, `Escalation Rule`
- `Human Review Required`, `Suggested Next AI`, `Touched Files`, `Risks`, `Commands Run`, `Notes`

既存 relay は追加 v2 スコープを `Notes` の `Critical Scope Information` ブロックとして保存する。`generate_handoff_prompt.py` はこのブロックを読み、Prompt の先頭に `Critical Scope Information` を表示する。

`--write-handoff` は `--output <path>` の指定を必須とし、指定先への Markdown ファイルのローカル生成だけを行う。`--output` がない場合はエラー終了し、実行ディレクトリへ生成物を作成しない。Notion 書き込みは行わず、AI Handoff DB 登録は、人間がドラフトを確認した後に既存 relay を明示的に実行する。

## Notionスキーマ方針

本 MVP は AI Consensus Log または AI Handoff DB のスキーマを変更しない。`Human Review Required` や追加の v2 安全情報を新規 DB フィールドとして追加せず、Markdown と既存 `Notes` 保存導線で保持する。

## 今回やらないこと

- Request Inbox 実装
- Router v1 本実装または自動実行
- 完全自動開発、PR 自動マージ、`git push`
- Notion スキーマ変更、`.env` 編集、API キー表示
- Render、Billing、GitHub Settings / Secrets / Actions の変更
- JSONL Event Store 全面移行、HumanLayer / OpenClaw 導入
- Claude Code Routines 本格化、DeepResearch 移管、タスクスケジューラ変更

## 実テスト対象

- Title: `AI引き継ぎシステム（AI Handoff / Relay）および分散AI運用について、この後どのように進めるべきか`
- Page ID: `3635ae2b-8d6a-81d6-bb2d-f806f8d6e4f8`
- 期待分類: `dev_task`
- 期待安全フラグ: `human_review_required = true`

期待理由は、Router v1 / `select_ai` / fallback prompt などの開発候補を含む一方、`attempt_count` / `fallback_triggered` の Notion DB フィールド追加案を含む可能性があり、Notion スキーマ変更は人間承認に戻す必要があるためである。

## 使い方

Processor は環境変数または既存 `.env` ロード結果の `NOTION_TOKEN` を読み、内容を表示しない。

```powershell
cd C:\Users\smsk5\Documents\personal_os_consensus
python meeting_result_processor.py --page-id 3635ae2b-8d6a-81d6-bb2d-f806f8d6e4f8 --dry-run
```

確認後、テスト用タスク名で Markdown を生成する。

```powershell
python meeting_result_processor.py --page-id 3635ae2b-8d6a-81d6-bb2d-f806f8d6e4f8 --write-handoff --task-title "[TEST] Meeting Result Processor MVP - dev_task handoff" --output C:\tmp\meeting_result_processor_mvp_handoff.md
```

人間確認後に既存 relay で登録し、出力された page ID から Prompt を生成する。

```powershell
python relay\create_handoff_page.py --from-file C:\tmp\meeting_result_processor_mvp_handoff.md
python relay\generate_handoff_prompt.py --page-id <created-handoff-page-id> --output C:\tmp\meeting_result_processor_mvp_prompt.md
```

生成 Prompt は `## Critical Scope Information` が先頭の作業情報ブロックとして表示され、対象 repo、作業ディレクトリ、許可ファイル、禁止事項、受入条件、停止条件を次 AI に先に伝える。
