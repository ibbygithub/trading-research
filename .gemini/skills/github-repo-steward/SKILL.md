# GitHub Repo Steward — v0.1
**Applies to:** Antigravity (Google Gemini)  
**Mirror:** `.claude/skills/github-repo-steward/SKILL.md` (near-identical; tool differences marked)  
**Last updated:** Session 14 (2026-04-17)

---

## Purpose

This skill defines the branch naming convention, commit message format, PR template, and acceptance checklist for every session branch in `trading-research`. Every session uses this skill — it is not optional. Using the skill is the acceptance test for it.

---

## Branch Naming

```
session/NN-<short-kebab-name>
```

Examples:
- `session/14-repo-census`
- `session/15-indicator-census`
- `session/16-feature-war-chest`

Rules:
- Always branch off `develop`, never off `main`
- Session number matches the plan in `docs/session-plans/`
- Kebab-case only; no underscores; no uppercase

```bash
# Antigravity — create and switch to branch
git checkout develop
git checkout -b session/NN-<name>
```

---

## Commit Message Format

```
<type>(session-NN): <short imperative description under 72 chars>

<body: what changed and why — 1-3 sentences. Why this change, not what it is.>

Co-Authored-By: Antigravity (Gemini) <noreply@google.com>
```

**Types:**
| Type | When to use |
|---|---|
| `feat` | New capability, new file, new deliverable |
| `fix` | Bug fix or correction to existing behavior |
| `chore` | Configuration, build, tooling, .gitignore |
| `docs` | Documentation only |
| `test` | Test additions or fixes |
| `refactor` | Code restructure with no behavior change |

**Rules:**
- One commit per logical deliverable
- Imperative present tense: "add" not "added"
- Body required for any decision or tradeoff

---

## PR Template

```markdown
## Session NN — <Session Name>

### Summary
- <bullet: what was built>
- <bullet: what was changed>
- <bullet: key decision made>

### Deliverables
- [ ] All deliverables exist at specified paths (from session plan)
- [ ] `uv run pytest` passes
- [ ] `docs/handoff/current-state.md` updated
- [ ] `docs/handoff/open-issues.md` updated
- [ ] `docs/handoff/next-actions.md` updated
- [ ] Work log at `outputs/work-log/YYYY-MM-DD-HH-MM-summary.md`

### Pipeline robustness change
none / <describe if any pipeline code was modified>

### Open issues created
none / <list new OI-NNN entries>

### Known limitations
none / <anything partially done, anything deferred>

🤖 Generated with Antigravity (Google Gemini)
```

---

## Acceptance Checklist

Before opening a PR, verify each item:

- [ ] Branch is `session/NN-<name>` off `develop`
- [ ] All session plan deliverables exist at their specified paths
- [ ] `uv run pytest` exits 0
- [ ] No `.env`, credentials, or secrets in any changed file
- [ ] `git diff develop...HEAD` shows a reviewable diff
- [ ] `docs/handoff/` files updated
- [ ] Work log written
- [ ] PR body uses the template above

---

<!-- TOOL-SPECIFIC: ANTIGRAVITY ONLY -->
## Tool-Specific Notes (Antigravity)

Use Antigravity's native git tooling or subprocess calls for all git operations. The `gh` CLI is available on the host. PR creation via GitHub API is also an option.

```bash
# Verify tests
uv run pytest

# Check diff
git diff develop...HEAD --stat

# Open PR
gh pr create --base develop --title "session/NN: <title>" --body "<body>"
```

Note: Antigravity does not have access to the Claude Code MCP GitHub tools. Use `gh` CLI or direct GitHub API calls.
<!-- END TOOL-SPECIFIC -->
