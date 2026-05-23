# Router Rules (minimal)

Maps a meeting result / handoff task to a candidate AI executor.

| Condition                                       | Candidate AI       |
|-------------------------------------------------|--------------------|
| Code change inside a Git-managed repo           | Codex              |
| Windows local / not Git-managed                 | Antigravity        |
| Long-form design document                       | Claude / GPT       |
| Notion organization / restructure               | Claude / GPT       |
| GitHub / Render UI operations                   | Claude for Chrome  |
| APIキー / Billing / .env / 本番削除             | Human (mandatory)  |

## Precedence

1. If the task touches APIキー / Billing / .env / 本番削除 → **Human**.
2. Else apply the first matching row above.
3. If nothing matches → leave `To AI: not determined` and escalate.
