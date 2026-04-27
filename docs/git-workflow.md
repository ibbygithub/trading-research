# Git Workflow — Trading Research Platform

**Purpose:** Define branching, commit cadence, and the rules for when code moves from `develop` to `main`. This applies to every agent and every session.

---

## Branch model

```
main                    ← promoted milestones only (see "main promotion rules" below)
  ↑
develop                 ← integration branch; agents commit and push here
  ↑
session-NN-<slug>       ← per-session feature branches; open a PR to develop
```

### Rules

1. **Agents never commit directly to `main`.** Per CLAUDE.md: "The human merges to main; agents do not."
2. **Agents never commit directly to `develop`.** Create a feature branch per session.
3. **Branch naming:** `session-<N>-<short-slug>` (e.g. `session-23a-instrument-featureset`, `session-D1-loss-limits`).
4. **PRs go feature branch → develop.** Agents open the PR; the human reviews and merges.
5. **`develop` → `main` is a human-only operation** gated by the promotion rules below.

---

## Commit cadence within a session

- Commit logical chunks, not every file. One commit per acceptance criterion is a good rhythm.
- Commit messages follow the pattern:
  ```
  <type>(session-NN): <imperative subject, lowercase, no period>

  <optional body: what changed and why, references to issues>
  ```
  Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `perf`.

- Every session ends with one docs commit for the work log:
  ```
  docs(session-NN): work log, updated handoff docs
  ```

- Push the feature branch to `origin` after every 2–3 commits. Do not wait until session end. This is your backup.

### Files to never stage blindly

Never use `git add -A` or `git add .`. Always stage explicit paths. These in particular need care:

- `configs/*.yaml` — may contain API keys or credentials (should not, but verify).
- `.env` or `.env.local` — never commit.
- `runs/.trials.json` — OK to commit; this is part of the provenance record.
- `outputs/work-log/` — OK to commit; this is the session log.
- `outputs/` besides work-log — case by case. Large binary artifacts should not be committed unless they're documentation.
- `data/raw/`, `data/clean/`, `data/features/` — use `.gitignore` to exclude parquet files; only manifest JSON is typically committed.

Check `.gitignore` before every session. If a session needs to commit a new artifact type, update `.gitignore` explicitly.

---

## Pushing a feature branch

```bash
# From project root, on your session feature branch
git status                              # verify clean or intended state
git add <specific-files>                # never -A
git commit -m "feat(session-NN): ..."
git push -u origin session-NN-<slug>    # first push
# subsequent pushes: git push
```

### Opening a PR from agent

Agents open the PR via `gh pr create` with the body describing what shipped and which acceptance tests pass. Human reviews and merges.

```bash
gh pr create \
  --base develop \
  --title "session-NN: <title>" \
  --body "$(cat <<'EOF'
## Summary
- <one-bullet per major change>

## Acceptance tests
- [x] pytest passes
- [x] <specific test>
- [x] ruff clean

## Persona reviews
- Architect: <concurred | requested changes>
- Data scientist: <concurred | requested changes>
- Mentor: <concurred | optional>

## Work log
outputs/work-log/YYYY-MM-DD-session-NN.md
EOF
)"
```

---

## Main promotion rules

`develop` → `main` is the gate. It is only done when one of the following is true:

### Milestone promotion

- **End of a track** — when Track A, C, E, G, or H is marked complete by all three personas, the current `develop` state is promoted to `main` with a version tag.

### Mid-track promotion

- **Before a session that changes load-bearing architecture** — if the next session is going to modify something structural, promote the current `develop` to `main` first so there's a clean rollback point.

### Pre-live promotion

- **Before the first live trade** — `main` must be a known-good state the day before live execution. Promote `develop` to `main` after the pre-live review sign-off.

### Safety promotion

- **At least once per calendar month** — to avoid `develop` drifting far from `main` and losing the archival benefit of `main`. Even without a milestone, bump `main` forward on a recurring basis.

### How to promote

```bash
git checkout main
git pull origin main
git merge --no-ff develop -m "merge: promote develop → main at session NN"
git tag -a v0.<track>.<N> -m "<description>"
git push origin main --tags
```

Never force-push to `main`. Never rebase `main`.

---

## Rollback protocol

If a merge to `main` turns out to be broken:

1. **Do not force-push `main`.** Create a revert commit:
   ```bash
   git revert -m 1 <merge-commit-sha>
   git push origin main
   ```
2. Open an issue documenting the revert reason.
3. Fix on `develop`, re-promote when fixed.

---

## Current state remediation (as of 2026-04-19)

`develop` is ~10 commits ahead of `main`. There is also uncommitted and untracked work on `develop`. Before the next session (23-a) starts, the state needs to be cleaned up:

### Step 1 — Commit or stash the work currently on develop

Modified files and untracked files fall into two buckets:

**Safe to commit to develop:**
- `.claude/rules/platform-architect.md` — new persona, belongs in the repo.
- `docs/roadmap/*` — new roadmap docs and session specs.
- `docs/handoff/*` — updated handoff docs.
- `configs/calendars/*.yaml` — event calendars.
- `configs/strategies/*.yaml` — strategy configs.
- `data/clean/*.manifest.json` — pipeline artifacts (manifests only, not parquets).
- `runs/.trials.json` — trial registry changes.

**Skill docs (`.claude/skills/`, `.gemini/skills/`) — ambiguous:**
- If these are meant to be shared across sessions, commit them to develop.
- If they're auto-generated or user-specific, add to `.gitignore`.

**Do not commit:**
- `data/clean/*.parquet` (if any) — binary artifacts, too large; use `.gitignore`.
- `.claude/settings.local.json` — per OI-003, this is tracked and should not be. Add to `.gitignore`, remove from tracking.

### Step 2 — Push develop to origin

After committing, push:

```bash
git push origin develop
```

This is the backup. From this point forward, every pushed feature branch is also backed up.

### Step 3 — Decide on main promotion

**Recommendation:** Do NOT promote to `main` right now. `develop` is in an in-between state — no strategy has passed the gate, the hardening sprint hasn't started. The next natural promotion point is after Track A completes (after session 28).

**Alternative:** If you want a `main` bump for archival purposes, promote now with the understanding that `main` represents "end-of-session-22 state, before the hardening sprint" — and tag it as such: `v0.pre-hardening`.

---

## Cheat sheet — common scenarios

### Starting a new session

```bash
git checkout develop
git pull origin develop
git checkout -b session-NN-<slug>
# do the work
```

### Mid-session checkpoint

```bash
git add <specific-files>
git commit -m "feat(session-NN): <subject>"
git push   # after first push, -u not needed
```

### End of session

```bash
# Work log
vim outputs/work-log/YYYY-MM-DD-session-NN.md
git add outputs/work-log/YYYY-MM-DD-session-NN.md
git commit -m "docs(session-NN): work log"
git push

# PR
gh pr create --base develop --title "session-NN: <title>" --body "..."
```

### Abandon a session that didn't work out

```bash
# On the feature branch, document why in a work log
git add outputs/work-log/YYYY-MM-DD-session-NN.md
git commit -m "docs(session-NN): abandoned, reason: ..."
git push
# Do NOT merge. The branch stays as historical record. Open a follow-up if needed.
```
