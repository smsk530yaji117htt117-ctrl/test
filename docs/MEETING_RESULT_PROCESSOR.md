# Meeting Result Processor

MVP that turns an AI Consensus Log meeting result into a Handoff v2 task
Markdown, which can then be fed into `relay/create_handoff_page.py` and
`relay/generate_handoff_prompt.py`.

## Usage

```
python meeting_result_processor.py --from-file path/to/meeting.md
# optional (not implemented in MVP):
python meeting_result_processor.py --page-id <AI Consensus Log page id>
```

Output is printed to stdout:

```
category: dev_task
handoff:  generated_handoffs/handoff_from_meeting_YYYYMMDD_HHMMSS.md
```

## Categories

| Category        | Trigger keywords (examples)                                  |
|-----------------|--------------------------------------------------------------|
| `dev_task`      | 実装 / 修正 / コード / PR / スクリプト / ファイル / 関数 / テスト / バグ |
| `research_task` | 調査 / 比較 / 確認 / リサーチ / 情報収集 / 検証                 |
| `human_review`  | 承認 / 支払い / APIキー / 削除 / 本番 / Billing / .env / Secrets / 環境変数 / カード / 課金 |
| `no_action`     | none of the above                                            |

**Precedence:** if any `human_review` keyword is present, the result is
`human_review` even when `dev_task` keywords also match.

## Output

For `dev_task` only, a Handoff v2 Markdown is written to
`generated_handoffs/handoff_from_meeting_<timestamp>.md` with these
fields (unknowns are filled with `not determined` or
`Human review required`):

Task, Status, From AI, To AI, Repository, Working Directory,
Target Files, Execution Environment, Git Managed, Goal, Current State,
Next Action, Do Not Touch, Acceptance Criteria, Escalation Rule,
Touched Files, Risks, Commands Run, Notes.

## Downstream

```
python relay/create_handoff_page.py --from-file <generated markdown>
python relay/generate_handoff_prompt.py --page-id <created page id>
```

## Not yet

- `--page-id` (Notion fetch)
- LLM-based classification
- Auto-routing to `relay/*` scripts
