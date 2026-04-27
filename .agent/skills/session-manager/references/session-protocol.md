# Session Management & Work-Log Protocol

This document defines the technical enforcement for session transitions, originally migrated from the legacy `settings.local.json` hooks.

## Work-Log Validation Logic
To satisfy the "Stop" hook requirement, the agent must ensure the following directory and file state exists before termination:

- **Directory**: `outputs/work-log/`
- **Validation Command**: 
  ```bash
  find outputs/work-log -name '*.md' -mmin -120 2>/dev/null | head -1
Action: If the command returns empty, the agent has failed the "Stop" hook and must remediate by writing the log.

Mandatory Work-Log Template
All logs must follow this structure exactly, as defined in the Project Constitution:

Session Summary — YYYY-MM-DD HH:MM
Completed
[One line per item]

Files changed
[path/to/file] — [reason]

Decisions made
[Architectural/Statistical rationale]

Next session starts from
[Specific project state for the next agent]

Review Criteria
Before the log is finalized, the Trio must provide a "Review Checkpoint":

Architect: Is the code maintainable and decoupled?

Scientist: Is the evidence for this session's work statistically honest?

Mentor: Does this session move us closer to the "Trader's Desk" finish line?


---

### Verification Checklist
To ensure your Notepad++ copy is correct, verify that these are the **last three lines** of the file:
1. `- **Architect**: Is the code maintainable and decoupled?`
2. `- **Scientist**: Is the evidence for this session's work statistically honest?`
3. `- **Mentor**: Does this session move us closer to the "Trader's Desk" finish line?`

