# Human Review Required Policy

## 目的

この文書は、Handoff v2 に `human_review_required = true` が記録された場合の運用ルールを定める草案である。

Meeting Result Processor が `dev_task` を生成できる場合でも、安全性、権限、秘密情報、外部サービスまたは本番影響に関わる判断が残るときは、次 AI が即実装へ進まないための停止ゲートとして扱う。

このポリシーは人間承認つきの半自動導線を定義するものであり、自動実行、Router v1 実装、Notion スキーマ変更を認めるものではない。

## `human_review_required = true` の定義

`human_review_required` は `classification` とは別の安全フラグである。

- `classification = dev_task` かつ `human_review_required = false`: Handoff のスコープと受入条件が十分であれば、通常のレビュー後に次 AI へ渡せる候補である。
- `classification = dev_task` かつ `human_review_required = true`: 実装候補は存在するが、ユーザー本人の承認が得られるまで実装 AI へ投入してはいけない。
- `classification = human_review`: 実装範囲そのものが未確定であり、人間判断を先に完了させる必要がある。

`human_review_required = true` は、AI がリスクを説明し、選択肢を整理し、推奨判断を提示することを許す。一方で、承認対象の作業を実行する許可にはならない。

## 最終承認者

`human_review_required = true` の最終承認者はユーザー本人である。

- AI は承認の代行をしない。
- 別の AI による同意、レビュー完了、推奨判断はユーザー承認の代替にならない。
- 実装 AI への最終投入、保護対象に関する操作許可、Status を `Ready` として扱う判断は、ユーザー本人の明示承認後にのみ行う。
- 承認内容が曖昧な場合、AI は `Human Review` で停止し、承認範囲を確認する。

## AI ができること / できないこと

### できること

- 会議結果、Handoff v2、関連 docs、差分および検証結果を読み取り確認する。
- リスク、保護対象、必要な承認事項、選択肢を整理する。
- 実装範囲、Target Files、Acceptance Criteria、Escalation Rule の草案を提案する。
- ユーザー承認前に安全なレビュー、調査、docs 草案作成を行う。ただし Handoff の `Do Not Touch` と個別指示に従う。
- 承認後に、明示された範囲だけを次 AI 用 Handoff として整える。

### できないこと

- ユーザー本人の承認を推定、代替または省略する。
- `Human Review` のまま実装 AI に作業開始を指示する。
- 保護対象の変更を「必要そうである」ことだけを理由に実行する。
- 秘密情報を表示、転記、ログ出力または Handoff 本文へ複製する。
- 自動的に push、PR merge、デプロイまたは本番削除を実行する。

## 必ず人間承認に戻す条件

次のいずれかを含む作業は、具体的な `dev_task` が存在しても `human_review_required = true` とし、ユーザー本人の承認まで停止する。

- Notion スキーマ、データベースのプロパティ、Status 選択肢、フィールドの追加・型変更・削除
- `.env` の編集、API キー、token、credential、secret の表示・作成・変更・移動
- Render 設定、デプロイ設定、環境変数、本番サービスまたは本番データへの変更
- Billing、GitHub Settings、GitHub Secrets、GitHub Actions 設定への変更
- `git push`、PR merge、PR 自動マージ、リポジトリ削除または本番削除
- Router または自動実行の有効化に伴う権限・安全性判断
- Target Files 外の編集、source of truth が不明な変更、復旧方法が不明な作業

調査または docs 作成のみで保護対象を変更しない場合でも、実装許可まで自動的に拡張してはならない。

## Handoff Status 運用

次の Status は、Handoff を人間承認つきで運用するための暫定的な状態ラベルである。

| Status | 意味 | 次 AI の扱い |
| --- | --- | --- |
| `Draft` | 生成直後。内容・スコープ・リスクが未確認 | まだ AI に渡さない |
| `Human Review` | ユーザー本人の承認待ち。`human_review_required = true` はここで停止 | 読み取り、レビュー、承認準備のみ |
| `Ready` | ユーザー本人が作業範囲と停止条件を承認済み | 明示された範囲で次 AI へ渡してよい |
| `In Progress` | 承認済みの範囲で次 AI が作業中 | 追加リスクが出たら `Human Review` に戻す |
| `Done` | 作業または検証が完了し、結果が報告済み | 完了証跡として保持する |
| `Archived` | 検証証跡、旧タスクまたは作業対象外 | 削除せず参照用に保存する |

この表は運用上の草案であり、Notion の Status 選択肢またはスキーマを変更する指示ではない。既存 DB がこれらの値を保持できない場合は、既存で利用可能な Status を維持し、承認待ち状態とユーザー承認結果を Handoff 本文または既存 `Notes` 導線に記録する。スキーマ変更が必要に見える場合は、変更せず人間承認に戻す。

## Escalation Rule

`human_review_required = true` の Handoff では、次のルールを最低限記載し、満たせない場合は作業を停止する。

```text
Stop before implementation until the user explicitly approves the task scope and protected actions.
Stop before any Notion schema change, .env or secret handling, Render or production change, Billing or GitHub settings change, git push, or PR merge.
Stop if work outside Target Files is required, the source of truth is unclear, or acceptance criteria cannot be verified safely.
```

停止時の報告には、確認済みの事実、承認が必要な事項、推奨する次の判断、承認後に許可される具体的範囲を短く記載する。

## 次 AI へ渡す前のチェックリスト

`human_review_required = true` の作業を `Ready` として次 AI へ渡す前に、以下を確認する。

- [ ] Handoff に `classification` と `human_review_required = true` の理由が記載されている。
- [ ] Repository、Working Directory、Target Files、Execution Environment、Git Managed が明示されている。
- [ ] `Do Not Touch` と Escalation Rule が具体的に記載されている。
- [ ] Notion スキーマ、`.env`、秘密情報、Render、Billing、GitHub 設定、`git push`、PR merge の扱いが明記されている。
- [ ] Acceptance Criteria が安全に検証可能である。
- [ ] ユーザー本人が、許可する作業範囲と禁止事項を明示的に承認した。
- [ ] 承認後の作業が Target Files 内に限定されている、または追加範囲がユーザーに承認されている。
- [ ] 次 AI が開始前に読むべき `Critical Scope Information` が Handoff に含まれている。
- [ ] Notion スキーマ変更なしで承認記録と安全条件を保持できる。

いずれかが満たされない場合、Status は `Human Review` のままとし、次 AI に実装開始を指示しない。

## 具体例

### 例1: 実装候補と Notion フィールド追加案が混在する

会議結果に Router 関数や fallback prompt の実装候補があり、同時に `attempt_count` や `fallback_triggered` のフィールド追加案が含まれる場合:

```text
classification = dev_task
human_review_required = true
Status = Human Review
```

AI はコード候補とリスクを整理できるが、Notion スキーマを変更せず、ユーザーが安全な実装範囲を承認するまで次 AI に着手させない。

### 例2: `.env` または API キーを必要とする修正

コード変更自体が明確でも、`.env` の編集や API キー値の確認・表示が必要とされる場合:

```text
classification = dev_task
human_review_required = true
Status = Human Review
```

AI は secret 値を表示せず、必要な権限判断と代替手順を提示して停止する。

### 例3: docs のみで保護対象を変更しない作業

既存ルールを説明する docs を作成し、Notion スキーマや設定を変更しないことが明示され、Target Files と受入条件が確定している場合、Handoff のレビュー後に通常の docs タスクとして扱える。ただし、docs の内容が将来の保護対象変更を提案しても、その変更自体は別途 `Human Review` で止める。

## 今回やらないこと

- Router v1 本実装、Request Inbox 実装、自動開発または自動ルーティングの導入
- PR 自動マージ、PR merge、`git push` の自動許可
- Notion スキーマ、AI Consensus Log または AI Handoff DB のフィールド・Status 選択肢変更
- `.env` 編集、API キーまたは secret の表示・移動
- Render、Billing、GitHub Settings / Secrets / Actions の変更
- 本番削除、タスクスケジューラ変更、JSONL Event Store 全面移行
- HumanLayer / OpenClaw 導入、Claude Code Routines 本格化、DeepResearch 移管

本草案は docs による運用合意の土台であり、いずれの保護対象操作も承認または実行しない。
