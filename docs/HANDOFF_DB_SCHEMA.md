# AI Handoff DB Schema

This document defines the minimum Notion database schema for handing work from one AI agent to another.

The first implementation is intentionally semi-automatic:

1. A human writes the handoff state into Notion.
2. Codex reads one AI Handoff row.
3. Codex generates a prompt that can be pasted into GPT/Codex, Gemini, or another AI worker.

This system is separate from the existing AI Consensus Log. Do not reuse or modify the AI Consensus Log schema for handoff records.

## Minimum Properties

| Property | Type | Required | Purpose |
| --- | --- | --- | --- |
| `Task` | Title | Yes | Short name of the handoff task. |
| `Status` | Select | Yes | Suggested values: `Draft`, `Ready`, `Handed Off`, `Done`. |
| `From AI` | Select | No | Agent that is handing off the work, such as `Claude Code`, `Codex`, or `Gemini`. |
| `To AI` | Select | No | Target agent, such as `Codex`, `GPT`, or `Gemini`. |
| `Repository` | Rich text | Yes | Local repository path or repository name. |
| `Branch` | Rich text | No | Current git branch, if relevant. |
| `Goal` | Rich text | Yes | The final user-visible outcome. |
| `Current State` | Rich text | Yes | What is already understood or completed. |
| `Next Action` | Rich text | Yes | The first concrete action the next AI should take. |
| `Touched Files` | Rich text | No | Files already changed or likely to be changed. |
| `Do Not Touch` | Rich text | No | Files, schemas, secrets, or operations that are out of scope. |
| `Risks` | Rich text | No | Known risks, uncertainty, or approval requirements. |
| `Commands Run` | Rich text | No | Relevant commands already executed and their outcomes. |
| `Notes` | Rich text | No | Extra context that does not fit elsewhere. |
| `Updated` | Date | No | Last human update time. |

## Status Meaning

| Status | Meaning |
| --- | --- |
| `Draft` | Handoff information is still incomplete. |
| `Ready` | The row is ready to generate a handoff prompt. |
| `Handed Off` | A prompt has been generated and handed to another AI. |
| `Done` | The handed-off task has been completed or closed. |

## Environment Variable

For future database-level lookup, use:

```text
NOTION_HANDOFF_DATA_SOURCE_ID=<notion data source id>
NOTION_HANDOFF_DATABASE_ID=<notion database id>
```

Prefer `NOTION_HANDOFF_DATA_SOURCE_ID` for new page creation. `NOTION_HANDOFF_DATABASE_ID` is kept as a fallback when a data source ID is not available.

The prompt generator supports direct page lookup with `--page-id`, so these variables are optional for prompt generation.

## Safety Rules

- Do not store API keys, tokens, or other secrets in the handoff database.
- Keep `Do Not Touch` explicit when the task has protected files.
- Prefer a new handoff record over editing unrelated Consensus Log records.
- Do not mark `Status` as `Handed Off` automatically in the minimum version.
