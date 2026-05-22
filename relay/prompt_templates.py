"""Prompt templates for AI handoff generation."""

from __future__ import annotations


def build_gpt_handoff_prompt(fields: dict[str, str]) -> str:
    """Build a paste-ready handoff prompt from normalized Notion fields."""
    task = fields.get("Task") or "(untitled handoff task)"
    critical_scope_fields = [
        "Repository",
        "Working Directory",
        "Target Files",
        "Execution Environment",
        "Git Managed",
        "Do Not Touch",
        "Acceptance Criteria",
        "Escalation Rule",
    ]
    notes = fields.get("Notes") or ""
    notes_scope: dict[str, str] = {}
    notes_lines = notes.splitlines()

    for index, line in enumerate(notes_lines):
        if line.strip() != "## Critical Scope Information":
            continue

        current_field: str | None = None
        pending_blank = False
        for block_line in notes_lines[index + 1 :]:
            stripped = block_line.strip()
            if stripped.startswith("## "):
                break

            matched_field = None
            inline_value = ""
            for field in critical_scope_fields:
                prefix = f"{field}:"
                if stripped == prefix or stripped.startswith(prefix):
                    matched_field = field
                    inline_value = stripped[len(prefix) :].strip()
                    break

            if matched_field:
                current_field = matched_field
                pending_blank = False
                notes_scope.setdefault(current_field, "")
                if inline_value:
                    notes_scope[current_field] = inline_value
                continue

            if not current_field:
                continue

            if not stripped:
                if notes_scope.get(current_field):
                    pending_blank = True
                continue

            if pending_blank and not block_line.startswith((" ", "\t", "-", "*")):
                break

            existing = notes_scope.get(current_field, "")
            notes_scope[current_field] = f"{existing}\n{block_line}".strip()
            pending_blank = False
        break

    def scope_value(field: str) -> str:
        value = (fields.get(field) or "").strip()
        if value and value != "(not provided)":
            return value
        return notes_scope.get(field) or "(not provided)"

    lines = [
        f"# AI Handoff: {task}",
        "",
        "You are taking over an in-progress coding task from another AI agent.",
        "Use the handoff state below as the source of truth, then inspect the repository before making changes.",
        "",
        "## Critical Scope Information",
        f"- Repository: {scope_value('Repository')}",
        f"- Working Directory: {scope_value('Working Directory')}",
        f"- Target Files: {scope_value('Target Files')}",
        f"- Execution Environment: {scope_value('Execution Environment')}",
        f"- Git Managed: {scope_value('Git Managed')}",
        f"- Do Not Touch: {scope_value('Do Not Touch')}",
        f"- Acceptance Criteria: {scope_value('Acceptance Criteria')}",
        f"- Escalation Rule: {scope_value('Escalation Rule')}",
        "",
        "## Handoff Metadata",
        f"- From AI: {fields.get('From AI') or 'Unknown'}",
        f"- To AI: {fields.get('To AI') or 'GPT/Codex'}",
        f"- Status: {fields.get('Status') or 'Unknown'}",
        f"- Repository: {fields.get('Repository') or 'Unknown'}",
        f"- Branch: {fields.get('Branch') or 'Unknown'}",
        "",
        "## Goal",
        fields.get("Goal") or "(not provided)",
        "",
        "## Current State",
        fields.get("Current State") or "(not provided)",
        "",
        "## Next Action",
        fields.get("Next Action") or "(not provided)",
        "",
        "## Files Already Touched or Likely Relevant",
        fields.get("Touched Files") or "(not provided)",
        "",
        "## Do Not Touch",
        fields.get("Do Not Touch") or "(not provided)",
        "",
        "## Risks and Approval Requirements",
        fields.get("Risks") or "(not provided)",
        "",
        "## Commands Already Run",
        fields.get("Commands Run") or "(not provided)",
        "",
        "## Additional Notes",
        fields.get("Notes") or "(not provided)",
        "",
        "## Instructions for the Next AI",
        "1. Start by reading the repository state and the files listed above.",
        "2. Do not change files listed in Do Not Touch.",
        "3. If the requested change affects protected files, stop and ask for human approval.",
        "4. Keep the implementation scoped to the Goal and Next Action.",
        "5. Report changed files, verification commands, and any remaining risks when done.",
    ]
    return "\n".join(lines).strip() + "\n"
