"""Prompt templates for AI handoff generation."""

from __future__ import annotations


def build_gpt_handoff_prompt(fields: dict[str, str]) -> str:
    """Build a paste-ready handoff prompt from normalized Notion fields."""
    task = fields.get("Task") or "(untitled handoff task)"
    lines = [
        f"# AI Handoff: {task}",
        "",
        "You are taking over an in-progress coding task from another AI agent.",
        "Use the handoff state below as the source of truth, then inspect the repository before making changes.",
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

