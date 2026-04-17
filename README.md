# trading-research

Personal quant trading research lab. See `CLAUDE.md` for the project spine
and operating contract. See `.claude/rules/` for the always-loaded personas
(quant mentor + data scientist) and `.claude/skills/` for on-demand skills.

## Quick reference

- **Environment:** Python 3.12 managed by `uv`. Run `uv sync --extra dev` on
  a fresh clone.
- **Tests:** `uv run pytest`
- **TradeStation credentials:** copy `.env.example` to `.env` and fill in.
  See `docs/running-the-downloader.md`.
- **Session plans:** `docs/session-plans/` holds the rolling build plan.
