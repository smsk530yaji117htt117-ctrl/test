# Handoff Standard v2

Handoff v2 is a standard Markdown format for passing work between AI agents and humans. It is not only a memo. It is a small work ticket that tells the next AI whether the task is safe to pick up, where the true working files are, and when to stop for human judgment.

This document is intentionally conservative. When the next action is unclear or unsafe, escalation is the correct result.

## 1. Purpose

Handoff v2 exists to prevent source-of-truth confusion.

The immediate problem is that one project can have multiple similar-looking files in different places. For example:

- `personal_os_consensus` is the Git repository used for AI meeting and handoff work.
- Some DeepResearch / Dispatcher scripts live directly under `C:\Users\smsk5` and are not managed by this Git repository.
- A `dispatcher.py` inside `personal_os_consensus` is not automatically the same source of truth as `C:\Users\smsk5\dispatcher.py`.

Handoff v2 therefore requires explicit fields for repository, working directory, target files, execution environment, Git status, protected files, and escalation rules before the goal is described.

## 2. Basic Philosophy

### Scope

Scope means the exact area where an AI is allowed to work.

A valid handoff must say:

- Which repository or folder is the source of truth.
- Which working directory commands should run from.
- Which files may be read or edited.
- Which files, services, or settings must not be touched.

If the scope is unclear, the AI must not guess.

### Work Definition

Work Definition means the task is concrete enough to execute.

A valid handoff must say:

- What the task is.
- What state the task is currently in.
- What the next action is.
- What acceptance criteria define completion.
- What commands have already been run.
- What files have already been touched.

### Safety Control

Safety Control means the handoff includes stop rules.

A valid handoff must say:

- When the AI may start work.
- When the AI must escalate instead of continuing.
- What risks are known.
- What must be reported back to a human.

Escalation is not failure. It is a correct stop state when the AI has reached the edge of its authority or confidence.

## 3. Standard Markdown Format

Use this exact section order for new handoff records. The source-of-truth and safety fields appear before `Goal` so an AI reads them before thinking about implementation.

```md
# Handoff v2

## Task

<short task name>

## Status

Draft | Ready | Handed Off | Done | Blocked

## Repository

<absolute local repository path, GitHub URL, or "Git管理外">

## Working Directory

<absolute directory where commands should run>

## Target Files

- <file or folder AI may edit>

## Execution Environment

- <OS>
- <runtime or shell>
- <important tools or scheduled execution context>

## Git Managed

Yes | No | Partial

## Do Not Touch

- <protected file, secret, setting, service, or operation>

## Acceptance Criteria

- <objective completion check>

## Escalation Rule

Escalate if any required scope, safety, or completion condition is unclear.

## Goal

<user-visible outcome>

## Current State

<what is known or already done>

## Next Action

<the first concrete action the next AI should take>

## AI-Ready Conditions

- [ ] Repository is explicit.
- [ ] Working Directory is explicit.
- [ ] Target Files are explicit.
- [ ] Execution Environment is explicit enough.
- [ ] Git Managed is Yes, No, or Partial.
- [ ] Do Not Touch is explicit.
- [ ] Acceptance Criteria are objective.
- [ ] Escalation Rule is present.

## Risks

- <known risk or uncertainty>

## Commands Run

- `<command>`: <result>

## Touched Files

- <file changed or inspected>

## Notes

<extra context>
```

## 4. Required And Optional Fields

### Required Fields

These fields are required in every Handoff v2 record:

- `Task`
- `Status`
- `Repository`
- `Working Directory`
- `Target Files`
- `Execution Environment`
- `Git Managed`
- `Do Not Touch`
- `Goal`
- `Current State`
- `Next Action`
- `Acceptance Criteria`
- `AI-Ready Conditions`
- `Escalation Rule`
- `Risks`
- `Commands Run`
- `Touched Files`
- `Notes`

Required does not mean the field must be long. If nothing was run yet, write `None yet`. If there are no known risks, write `No known risks beyond normal review`.

### Optional Fields

These fields are useful, but not required for the minimum v2 standard:

- `From AI`
- `To AI`
- `Branch`
- `Related Issue`
- `Related PR`
- `Due Time`
- `Raw Log`
- `Human Review Needed`

## 5. AI-Ready Conditions

AI-Ready is a condition checklist, not a new status value for now.

Use this pattern:

```text
Status:
Ready

AI-Ready Conditions:
All checklist items are satisfied. The AI may pick up the task only if every condition is true.
```

The AI may start work only when all of these are true:

- `Repository` identifies the correct source of truth.
- `Working Directory` matches where commands should run.
- `Target Files` identifies exactly what may be edited.
- `Execution Environment` is specific enough to avoid running commands in the wrong context.
- `Git Managed` is explicit.
- `Do Not Touch` lists protected files, secrets, services, and operations.
- `Acceptance Criteria` are objective enough to verify.
- `Escalation Rule` explains when to stop.
- The task can be completed without touching protected items.
- The task can be completed without changing Notion schema, GitHub settings, secrets, billing, actions, or task scheduler settings.

Use this table when a human or script needs a more mechanical readiness check:

| Check | Required | Pass Condition | Fail Action |
|---|---:|---|---|
| Repository | Yes | Explicit repository path, GitHub URL, or `Git管理外` is written. | Escalate |
| Working Directory | Yes | Absolute command directory is written. | Escalate |
| Target Files | Yes | At least one editable file or folder is written. | Escalate |
| Execution Environment | Yes | OS, runtime, shell, or scheduled context is specific enough to avoid running in the wrong place. | Escalate |
| Git Managed | Yes | Value is exactly `Yes`, `No`, or `Partial`. | Escalate |
| Do Not Touch | Yes | Field is not blank and protected files, secrets, services, or operations are listed. | Escalate |
| Acceptance Criteria | Yes | Completion can be checked objectively. | Escalate |
| Escalation Rule | Yes | Stop conditions are written. | Escalate |
| Current State | Yes | Existing state is clear enough to avoid repeating or undoing work. | Escalate |
| Next Action | Yes | First safe action is concrete. | Escalate |
| Commands Run | Yes | Previous commands are listed, or `None yet` is written. | Escalate |
| Touched Files | Yes | Changed or inspected files are listed, or `None yet` is written. | Escalate |

Future idea: add `AI-Ready` as a Notion `Status` option. Do not do that now. For the current version, keep Notion schema unchanged and represent AI readiness inside the handoff text.

## 6. Conditions Where AI Must Not Pick Up Work

An AI must not continue and must escalate when any of these are true:

- `Working Directory` does not match the actual folder.
- Editing outside `Target Files` is required.
- Multiple files have the same name and the source of truth cannot be identified.
- `Git Managed` is `No` or `Partial`, and save, backup, or recovery policy is unclear.
- The task requires touching anything listed under `Do Not Touch`.
- A Notion schema change is required.
- GitHub Settings, Secrets, Actions, or Billing must be touched.
- `git push` or PR merge is required.
- Task Scheduler settings must be changed.
- There are multiple plausible error causes and human judgment is needed.
- The AI cannot tell whether acceptance criteria are satisfied.

## 7. Escalation Rule

Escalation is the correct behavior when the AI cannot safely decide.

The AI should not treat escalation as failure. It should stop, explain what it confirmed, explain what is unclear, and offer options for a human decision.

Minimum rule:

```text
Escalate before editing when scope, source of truth, protected files, environment, or acceptance criteria are unclear.
Escalate before any action that writes outside Target Files or touches Do Not Touch.
Escalate before git push, PR merge, Notion schema changes, GitHub settings changes, secrets changes, billing changes, or task scheduler changes.
```

Use these categories when writing or reviewing an escalation rule.

### Scope Escalation

Escalate when the AI cannot safely identify where work should happen.

- `Working Directory` does not match the actual folder.
- Editing outside `Target Files` is required.
- Multiple files have the same name and the source of truth cannot be identified.

### Permission Escalation

Escalate when the task needs an action the AI is not allowed to take.

- Anything listed in `Do Not Touch` must be read, edited, moved, displayed, or deleted.
- `.env`, API keys, tokens, credentials, or secret-like values are involved.
- GitHub Settings, Secrets, Actions, Billing, or repository deletion must be touched.
- `git push` or PR merge is required.
- Task Scheduler settings must be changed.

### State Escalation

Escalate when the current state is unsafe or contradictory.

- `Git Managed` is `No` or `Partial`, and change, backup, save, or recovery policy is unclear.
- Existing state conflicts with the request.
- There are multiple plausible error causes and human judgment is needed.

### Completion Escalation

Escalate when the AI cannot prove the work is done.

- The AI cannot tell whether `Acceptance Criteria` are satisfied.
- Test or dry-run results are unclear.
- Required verification results for a completion report are missing.

## 8. Escalation Output Format

Use this Markdown when escalation is required:

```md
## Escalation Required

### Reason
-

### What I confirmed
-

### What is unclear
-

### Options
1.
2.
3.

### Recommended decision
-
```

Keep it short. The goal is to help the human decide quickly.

## 9. How To Write Risks, Commands, Files, And Notes

### Risks

Write risks as plain, concrete bullets.

Good:

```md
- `dispatcher.py` exists in more than one location. Source of truth must be confirmed before editing.
- Task Scheduler may call a script outside this repository.
```

Avoid vague risk notes such as `might be risky` without saying why.

### Commands Run

Record commands with outcomes.

```md
- `git status --short`: clean working tree.
- `python relay\generate_handoff_prompt.py --page-id ...`: not run because Notion credentials were not needed for this documentation task.
```

Do not paste secrets, tokens, or `.env` values into command output.

### Touched Files

Separate inspected files from changed files when useful.

```md
Changed:
- docs/HANDOFF_STANDARD_V2.md

Inspected:
- docs/HANDOFF_DB_SCHEMA.md
- relay/README.md
```

### Notes

Use `Notes` for context that helps, but does not belong in the stricter fields.

Good notes include:

- Human preference.
- Known naming confusion.
- Follow-up ideas.
- Why a tool was not run.

## 10. Example: AI Meeting / Handoff Work

```md
# Handoff v2

## Task

Improve AI meeting handoff prompt clarity

## Status

Ready

## Repository

C:\Users\smsk5\Documents\personal_os_consensus

## Working Directory

C:\Users\smsk5\Documents\personal_os_consensus

## Target Files

- consensus.py
- relay/
- docs/

## Execution Environment

- Windows
- PowerShell
- Repository virtual environment when Python execution is needed

## Git Managed

Yes

## Do Not Touch

- .env
- API keys
- Notion schema
- GitHub Secrets
- GitHub Settings
- git push
- PR merge

## Acceptance Criteria

- Handoff prompt clearly identifies repository, working directory, target files, and stop rules.
- Existing AI Consensus Log behavior is not changed unless explicitly requested.

## Escalation Rule

Escalate if the task requires Notion schema changes, secrets, git push, PR merge, or files outside Target Files.

## Goal

Make AI-to-AI handoff safer and easier to execute.

## Current State

The repository contains relay scripts and a handoff schema document. The current handoff format is useful but does not fully separate repository path, working directory, and target files.

## Next Action

Review the relay prompt template and propose a small docs-only improvement.

## AI-Ready Conditions

- [x] Repository is explicit.
- [x] Working Directory is explicit.
- [x] Target Files are explicit.
- [x] Execution Environment is explicit enough.
- [x] Git Managed is Yes.
- [x] Do Not Touch is explicit.
- [x] Acceptance Criteria are objective.
- [x] Escalation Rule is present.

## Risks

- Notion schema changes are out of scope.
- Existing encoded Japanese text in README may be unrelated and should not be edited in this task.

## Commands Run

- None yet.

## Touched Files

- None yet.

## Notes

This is Git-managed repository work. Keep changes small.
```

## 11. Example: DeepResearch / Dispatcher Work

```md
# Handoff v2

## Task

Investigate Dispatcher run behavior

## Status

Ready

## Repository

Git管理外

## Working Directory

C:\Users\smsk5

## Target Files

- C:\Users\smsk5\deep_research.py
- C:\Users\smsk5\dispatcher.py
- C:\Users\smsk5\dispatcher_log.txt

## Execution Environment

- Windows
- Existing venv or available Python
- Task Scheduler may reference these scripts

## Git Managed

No

## Do Not Touch

- C:\Users\smsk5\Documents\personal_os_consensus\dispatcher.py unless separately requested
- .env
- API keys
- Notion schema
- Task Scheduler settings
- GitHub Settings
- GitHub Secrets
- GitHub Actions
- Billing

## Acceptance Criteria

- The correct Dispatcher source of truth is identified.
- No script is moved or rewritten without human approval.
- If a change is needed, backup or recovery policy is confirmed first.

## Escalation Rule

Escalate before editing because Git Managed is No unless the human provides an explicit backup and recovery plan.

## Goal

Understand which Dispatcher script is actually used and what should happen next.

## Current State

There are similarly named files in different locations. `C:\Users\smsk5\dispatcher.py` is not the same as `C:\Users\smsk5\Documents\personal_os_consensus\dispatcher.py`.

## Next Action

Inspect file paths and scheduler references without editing anything. Report the source-of-truth finding.

## AI-Ready Conditions

- [x] Repository is explicit as Git管理外.
- [x] Working Directory is explicit.
- [x] Target Files are explicit.
- [x] Execution Environment is explicit enough.
- [x] Git Managed is No.
- [x] Do Not Touch is explicit.
- [x] Acceptance Criteria are objective.
- [x] Escalation Rule is present.

## Risks

- There may be no Git recovery path.
- Task Scheduler may depend on exact paths.
- Editing the wrong `dispatcher.py` would not fix the real runtime path.

## Commands Run

- None yet.

## Touched Files

- None yet.

## Notes

For Git-managed safety, consider moving future Dispatcher work into a repository only after human approval.
```

## 12. Git Managed: No / Partial Notes

`Git Managed` must be one of:

- `Yes`: changes are inside a Git repository and can be reviewed with `git diff`.
- `No`: changes are outside Git. There may be no easy recovery path.
- `Partial`: some files are Git-managed, but other required files or runtime settings are not.

When `Git Managed` is `No` or `Partial`, the AI must be extra cautious.

Before editing, the handoff should explain:

- How to back up files.
- How to restore files.
- Whether the task can be completed as inspection-only.
- Whether scheduler or external runtime paths may be affected.

If this is missing, escalate.

### Practical Rules For `Git Managed: No`

When files are not protected by Git history, the handoff must require extra recovery notes before editing.

- Make a backup before changing any file.
- Record the backup location.
- Write absolute paths in `Touched Files`.
- Write every executed command in `Commands Run`.
- Escalate if the restore method is unclear.

If the task can be completed by inspection only, prefer inspection and report findings without editing.

### Practical Rules For `Git Managed: Partial`

When only part of the work is Git-managed, the handoff must separate the two areas.

- Record Git-managed files separately from non-Git-managed files.
- Back up any non-Git-managed file before editing it.
- State which file or location is the source of truth.
- Escalate if it is unclear whether the Git-managed file or non-Git-managed file is authoritative.

Example:

```md
Touched Files

Git-managed:
- C:\Users\smsk5\Documents\personal_os_consensus\docs\example.md

Git管理外:
- C:\Users\smsk5\dispatcher.py
```

## 13. Do Not Touch Rules

`Do Not Touch` should be explicit and practical.

Include:

- Exact file paths when possible.
- Secret files such as `.env`.
- API keys, tokens, credentials, and logs that may contain secrets.
- Notion schema and production Notion pages.
- Task Scheduler settings.
- GitHub Settings, Secrets, Actions, Billing, and repository deletion.
- `git push` and PR merge when the AI is not allowed to do them.

Good:

```md
## Do Not Touch

- C:\Users\smsk5\deep_research.py
- C:\Users\smsk5\dispatcher.py
- .env
- API keys or tokens
- Notion schema
- Task Scheduler settings
- git push
- PR merge
```

Avoid vague entries like `important files`.

## 14. Temporary Notion Schema Policy

Do not add Notion schema fields right now.

For the current version:

- Keep `Status` values as the existing workflow supports them.
- Use `Status: Ready` plus `AI-Ready Conditions` in the Markdown body.
- Treat `AI-Ready` as a future Notion Status option, not an immediate schema change.
- If an AI thinks a schema change is required, it must escalate and propose the change instead of applying it.

This keeps the system stable while the handoff format is still being tested.

## 15. Future Improvements For Relay Scripts

Future work may update `relay/create_handoff_page.py` and `relay/generate_handoff_prompt.py`, but not as part of this docs-only task.

Possible improvements:

- Add support for the new v2 fields: `Working Directory`, `Target Files`, `Execution Environment`, `Git Managed`, `Acceptance Criteria`, `AI-Ready Conditions`, and `Escalation Rule`.
- Generate prompts that put source-of-truth and safety fields before `Goal`.
- Warn when required v2 fields are missing.
- Treat `AI-Ready Conditions` as body text until the Notion schema is intentionally changed.
- Add a validation mode that prints missing fields without writing to Notion.
- Keep backwards compatibility with existing v1 handoff pages.

Any script change should be a separate, small PR or task after this document is reviewed.

### Future `generate_handoff_prompt.py` Prompt Order

When `generate_handoff_prompt.py` is updated later, it should place this Critical Scope Information block at the very top of the generated prompt, before `Goal`, `Current State`, and `Next Action`.

```md
## Critical Scope Information

Repository:
<value>

Working Directory:
<value>

Target Files:
<value>

Execution Environment:
<value>

Git Managed:
<value>

Do Not Touch:
<value>

Acceptance Criteria:
<value>

Escalation Rule:
<value>
```

This order is intentional. The next AI should understand where it is allowed to work and when it must stop before it thinks about how to solve the task.

### Temporary `create_handoff_page.py` Storage Policy

Do not add Notion schema fields yet.

Until a separate schema-change task is approved, `create_handoff_page.py` should store the following v2 fields as structured Markdown inside `Notes` or `Current State`:

- `Working Directory`
- `Target Files`
- `Execution Environment`
- `Git Managed`
- `Do Not Touch`
- `Acceptance Criteria`
- `AI-Ready Conditions`
- `Escalation Rule`

This keeps the Notion database stable while still letting handoff pages carry the safer v2 information.
