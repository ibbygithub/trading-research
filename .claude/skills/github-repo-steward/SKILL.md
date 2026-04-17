# GitHub Repo Steward — v0.1
**Applies to:** Claude Code  
**Mirror:** `.gemini/skills/github-repo-steward/SKILL.md` (near-identical; tool differences marked)  
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
# Claude Code — create and switch to branch
git checkout develop
git checkout -b session/NN-<name>
```

---

## Commit Message Format

```
<type>(session-NN): <short imperative description under 72 chars>

<body: what changed and why — 1-3 sentences. Why this change, not what it is.>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
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
- One commit per logical deliverable (not one commit per file, not one mega-commit)
- Imperative present tense in the subject line: "add" not "added" or "adding"
- No period at end of subject line
- Body is optional for trivial changes; required for any decision or tradeoff

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

### Follow-up tickets
none / <OI-NNN: description>

🤖 Generated with [Claude Code](https://claude.ai/code)
```

---

## Acceptance Checklist

Before opening a PR, verify each item:

- [ ] Branch is `session/NN-<name>` off `develop`
- [ ] All session plan deliverables exist at their specified paths
- [ ] `uv run pytest` exits 0
- [ ] No `.env`, credentials, or secrets in any changed file
- [ ] `git diff develop...HEAD` shows a reviewable diff — not a wall of generated files
- [ ] Each commit has the `Co-Authored-By: Claude Sonnet 4.6` trailer
- [ ] `docs/handoff/` files updated (current-state, open-issues, next-actions)
- [ ] Work log written to `outputs/work-log/`
- [ ] PR body uses the template above

**Auto-merge posture:** If all checklist items are green and CI (when configured) is green, the PR may be merged without a blocking human review. Ibby retains the right to review any PR at his discretion — the checklist just does not *force* it.

---

## Tool-Specific Notes (Claude Code)

```bash
# Verify tests pass before opening PR
uv run pytest

# Check diff against develop before opening PR
git diff develop...HEAD --stat

# Open PR via GitHub MCP tool or gh CLI
gh pr create --base develop --title "session/NN: <title>" --body "$(cat <<'EOF'
<PR body here>
EOF
)"
```

The GitHub MCP tools (`mcp__github__create_pull_request`, `mcp__github__push_files`) are also available in this session if `gh` is not configured.
