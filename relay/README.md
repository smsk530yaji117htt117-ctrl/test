# AI Handoff Relay

`relay/` contains the minimum AI handoff tools.

It does not modify the existing AI Consensus Log.

## Usage

Create a handoff page from labeled Markdown:

```powershell
cd C:\Users\smsk5\Documents\personal_os_consensus
venv\Scripts\activate
python relay\create_handoff_page.py --from-file handoff_input.md
```

Optional title override:

```powershell
python relay\create_handoff_page.py --title "Claude Code上限後の引き継ぎ" --from-file handoff_input.md
```

Then generate a paste-ready prompt from the created page ID:

```powershell
python relay\generate_handoff_prompt.py --page-id <notion_page_id>
```

Optional file output:

```powershell
python relay\generate_handoff_prompt.py --page-id <notion_page_id> --output handoff_prompt.md
```

## Required Environment

The scripts read these values from the environment or from `.env` via `python-dotenv`.

```text
NOTION_TOKEN=<notion integration token>
NOTION_HANDOFF_DATA_SOURCE_ID=<ai handoff data source id>
```

`NOTION_HANDOFF_DATABASE_ID` is supported as a fallback when a data source ID is not available.

The relay scripts do not edit `.env`.

## Input Format

```text
Task:
Claude Code上限後の引き継ぎ

Status:
Ready

Repository:
local: C:\Users\smsk5\Documents\personal_os_consensus
github: 未確認

Goal:
ここに目的を書く

Current State:
ここに現状を書く

Next Action:
ここに次AIの最初の作業を書く

Do Not Touch:
.env、APIキー、git push

From AI:
Claude Code

To AI:
Codex

Raw Log:
ここにClaudeの最後の出力や作業ログを貼る
```

## Current Scope

- Creates a new AI Handoff page from a Markdown file.
- Writes short handoff fields to Notion properties.
- Writes `Raw Log` to the Notion page body.
- Prints the created page ID and URL.
- Reads one Notion page by `--page-id`.
- Extracts the minimum AI Handoff fields.
- Prints a GPT/Codex-ready handoff prompt.
- Does not update existing handoff pages.
- Does not automatically change handoff status after creation.
