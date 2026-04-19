---
name: project-layout
description: Use when scaffolding the trading-research repository, setting up the Python environment with uv, configuring tooling (ruff, pytest, structlog), creating new modules or packages, deciding where a piece of code or config belongs, or enforcing project-wide conventions. Invoke at the start of the project (initial scaffolding), when adding any new top-level component, when setting up the environment on a new machine, or when a question arises about file placement or naming conventions.
---

# Project Layout

This skill owns the physical and logical structure of the trading-research project: directories, the Python environment, tooling configuration, naming conventions, and the rules for where things live. It is the skill an agent loads at the very start of a session that will create new files or modify project structure, and the skill that answers "where does this go?"

The principle: **conventions exist so the human never has to think about plumbing.** If the layout is consistent and the tooling is automated, the human can focus on strategies and the agents can focus on implementation. Every minute spent debating "should this be in `src/` or `notebooks/`?" is a minute not spent on the actual work.

## What this skill covers

- Initial repository scaffolding (one-time setup)
- Python environment with `uv`
- Directory layout and naming conventions
- Tooling: `ruff`, `pytest`, `structlog`, `pyright` (optional)
- `pyproject.toml` structure
- `.gitignore` and what is and isn't committed
- Slash command definitions in `.claude/commands/`
- Conventions for configs, tests, notebooks, and runs

## What this skill does NOT cover

- Data schemas and storage layout (see `data-management`)
- Strategy implementation patterns (see `backtesting`)
- Anything about specific markets, instruments, or trading logic

## The repository layout

```
C:\trading-research\
├── CLAUDE.md                           # always-loaded project spine
├── README.md                           # human-facing project description
├── pyproject.toml                      # uv-managed deps + tool config
├── uv.lock                             # locked dependency versions (committed)
├── .python-version                     # python version pin (e.g. "3.12")
├── .gitignore
├── .ruff.toml                          # lint + format config
│
├── .claude/
│   ├── rules/
│   │   ├── quant-mentor.md             # always-loaded persona
│   │   └── data-scientist.md           # always-loaded persona
│   ├── skills/
│   │   ├── data-management/
│   │   │   └── SKILL.md
│   │   ├── project-layout/
│   │   │   └── SKILL.md
│   │   ├── historical-bars/
│   │   │   └── SKILL.md
│   │   └── ...                         # one folder per skill
│   └── commands/
│       ├── data-quality-check.md       # /data-quality-check slash command
│       ├── backtest-pessimistic.md
│       └── replay.md
│
├── configs/
│   ├── instruments.yaml                # contract registry (see data-management)
│   ├── strategies/
│   │   ├── zn_macd_rev_v1.yaml         # one file per strategy parameterization
│   │   └── ...
│   └── runs/
│       └── default.yaml                # default backtest run config
│
├── data/
│   ├── raw/                            # untouched downloads (gitignored)
│   ├── clean/                          # validated parquet (gitignored)
│   └── features/                       # resampled + indicators (gitignored)
│
├── src/
│   └── trading_research/               # importable Python package
│       ├── __init__.py
│       ├── data/
│       │   ├── __init__.py
│       │   ├── schema.py               # canonical bar schema
│       │   ├── instruments.py          # instrument registry loader
│       │   ├── validate.py             # calendar-based validation
│       │   ├── resample.py             # 1m → higher timeframe
│       │   └── trade_schema.py         # trade log schema
│       ├── ingest/
│       │   ├── __init__.py
│       │   └── tradestation.py         # historical + streaming
│       ├── indicators/
│       │   ├── __init__.py
│       │   ├── trend.py
│       │   ├── reversion.py
│       │   ├── volatility.py
│       │   └── orderflow.py
│       ├── strategies/
│       │   ├── __init__.py
│       │   ├── base.py                 # strategy interface
│       │   └── zn_macd_rev.py          # one file per strategy
│       ├── backtest/
│       │   ├── __init__.py
│       │   ├── engine.py               # event-driven simulation
│       │   ├── fills.py                # fill models
│       │   └── walkforward.py
│       ├── risk/
│       │   ├── __init__.py
│       │   ├── sizing.py               # vol targeting, etc.
│       │   └── limits.py               # daily/weekly stops
│       ├── eval/
│       │   ├── __init__.py
│       │   ├── metrics.py              # Sharpe, Sortino, Calmar, deflated
│       │   ├── reports.py              # one-page report generation
│       │   └── tests.py                # statistical tests
│       ├── replay/
│       │   ├── __init__.py
│       │   ├── app.py                  # Dash entrypoint
│       │   └── components.py
│       └── utils/
│           ├── __init__.py
│           ├── logging.py              # structlog setup
│           └── time.py                 # timezone helpers
│
├── notebooks/
│   └── .gitkeep                        # scratch space, not source of truth
│
├── tests/
│   ├── __init__.py
│   ├── test_schema.py
│   ├── test_validate.py
│   ├── test_resample.py
│   ├── test_indicators/
│   ├── test_backtest/
│   └── fixtures/
│       └── sample_zn_1m.parquet        # small fixture data for tests
│
├── runs/                               # backtest outputs (gitignored)
│   └── <run_id>/
│       ├── config.yaml                 # the exact config used
│       ├── trades.parquet              # trade log
│       ├── equity.parquet              # equity curve
│       ├── report.html                 # one-page evaluation report
│       └── log.jsonl                   # structured log of the run
│
└── scripts/
    ├── setup.py                        # one-shot environment setup
    └── new_strategy.py                 # scaffolds a new strategy file
```

## Why this layout

**`src/trading_research/` as an importable package, not a flat collection of scripts.** This is the single most important structural decision and it directly addresses the worst anti-pattern in the old code Ibby shared: a 700-line script with everything in one file. The package layout forces separation of concerns. Each module has one responsibility. Each can be unit-tested. Each can be imported from a notebook for exploration without dragging in the rest of the system. The cost is some upfront discipline; the benefit is that the code stays sane as it grows.

**`configs/` separate from code.** Strategies are parameterized by YAML files, not by Python defaults. The same strategy code runs against multiple configs, and switching parameters never requires editing source. This also makes runs reproducible — the config file used for a run is copied into `runs/<run_id>/config.yaml` so you can always answer "what exactly did I run?"

**`data/`, `runs/`, and `notebooks/` are gitignored.** None of this belongs in version control. Data is too large, runs are too numerous, and notebooks are scratch space. What gets committed: source code, configs, persona files, skill files, tests, fixtures. Everything else is local.

**`tests/` mirrors `src/` structure.** A function in `src/trading_research/data/validate.py` has tests in `tests/test_validate.py`. A subpackage like `indicators/` gets a `test_indicators/` directory. The mapping is automatic and obvious.

**Notebooks are explicitly second-class.** They live in a directory called `notebooks/`. The directory contains a `.gitkeep` and nothing committed. Anything that earns its keep gets promoted to `src/` with tests. This is a hard rule because the alternative — letting analysis code accumulate in notebooks — is how research projects rot.

## The Python environment with `uv`

`uv` is the project's package and environment manager. It is installed by the agent at first setup and then never thought about again.

**One-time setup, performed by the agent on a fresh clone:**

```bash
# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh    # Linux/macOS
# OR on Windows PowerShell:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# In the project directory
uv sync                  # creates .venv and installs locked dependencies
uv run pytest            # verifies the install by running the test suite
```

The agent does this. The human does not. If `uv` is missing, the agent installs it. If `.venv` is missing or stale, the agent recreates it. The human's only involvement is approving any operation that would touch their system Python or PATH.

**`pyproject.toml` skeleton:**

```toml
[project]
name = "trading-research"
version = "0.1.0"
description = "Personal quant trading research lab"
requires-python = ">=3.12"
dependencies = [
    # data
    "polars>=0.20",
    "pyarrow>=15.0",
    "pandas>=2.2",                       # for ecosystem compat
    "pandas-market-calendars>=4.4",
    "pyyaml>=6.0",

    # ingest
    "httpx>=0.27",
    "websockets>=12.0",
    "tenacity>=8.2",                     # retry logic

    # analysis
    "numpy>=1.26",
    "scipy>=1.12",
    "statsmodels>=0.14",
    "scikit-learn>=1.4",

    # visualization
    "plotly>=5.20",
    "dash>=2.16",
    "mplfinance>=0.12.10b0",

    # ops
    "structlog>=24.1",
    "click>=8.1",                        # CLI entry points
    "rich>=13.7",                        # nicer terminal output
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "ruff>=0.3",
    "pyright>=1.1.350",
]
ml = [
    "xgboost>=2.0",
    "lightgbm>=4.3",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/trading_research"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-ra -q --strict-markers"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "B", "UP", "SIM", "RET"]
ignore = ["E501"]                        # line length handled by formatter

[tool.pyright]
pythonVersion = "3.12"
include = ["src"]
strict = ["src/trading_research/data", "src/trading_research/backtest"]
```

The strict pyright zones are deliberate: data and backtest are the modules where type errors cause silent correctness bugs, so they get strict checking. Other modules get basic checking.

**Why these dependencies and not others:**

- **Polars over pandas as the primary dataframe library** because it's faster, has cleaner parquet handling, and its API encourages the kind of explicit, expression-based code that's easy to read in code review. Pandas stays in the dependency list because `pandas-market-calendars` requires it and some scipy/statsmodels code expects it.
- **httpx over requests** because it supports async, which matters for streaming and for parallel historical pulls.
- **structlog over the stdlib logging** because backtest runs need structured (JSON) logs that the replay app can ingest, not free-form text.
- **Click for CLI entry points** so that `uv run trading-research backtest --strategy zn_macd_rev_v1` works out of the box.
- **No `requirements.txt`.** `uv.lock` is the lockfile and it's committed. `requirements.txt` is legacy.

## Tooling

**Ruff for lint and format.** One tool, fast, opinionated. Replaces flake8, isort, black, and pyupgrade. Runs on save in any modern editor and via `uv run ruff check` / `uv run ruff format`.

**Pytest for tests.** Standard. The `tests/` layout uses function-based tests, not class-based, unless a fixture really benefits from class scoping. Fixtures live in `tests/fixtures/` (small parquet files, sample configs) and in `conftest.py` files (Python fixture definitions).

**Structlog for logging.** Configured once in `src/trading_research/utils/logging.py`. Backtest runs emit JSON-line logs that the replay app and the evaluation skill can parse. Never use `print()` in source code — only in CLI scripts and notebooks.

**Pyright for type checking.** Optional but recommended. Strict in `data/` and `backtest/` modules. Loose elsewhere. Catches the class of bugs where a function returns `None` and a downstream caller dereferences it — exactly the kind of bug that's painful in long-running backtests.

## `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
*.egg-info/
build/
dist/

# Project data and outputs
data/raw/
data/clean/
data/features/
runs/
notebooks/*.ipynb
notebooks/scratch/
!notebooks/.gitkeep

# Tooling
.pytest_cache/
.ruff_cache/
.coverage
coverage.xml
htmlcov/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Secrets
.env
.env.*
!.env.example
configs/secrets.yaml
```

**The notebook rule:** notebooks themselves are gitignored, but the `notebooks/` directory exists with a `.gitkeep`. This is deliberate. Notebooks are personal scratch space — they don't belong in shared version control where they create merge conflicts and store stale outputs. If a notebook produces something worth keeping, it gets refactored into `src/` with tests.

**The secrets rule:** TradeStation API credentials live in `.env` which is gitignored. A `.env.example` file (committed) shows the variable names without values. The agent reads `.env` at runtime via `os.environ`; the human creates `.env` once and never thinks about it again.

## Slash commands in `.claude/commands/`

Project-specific slash commands compress common workflows into one keystroke. Each command is a markdown file with a description and a body.

**Initial set:**

```
.claude/commands/
├── data-quality-check.md    # validates a dataset against the trading calendar
├── backtest-pessimistic.md  # runs a backtest with pessimistic defaults locked
├── replay.md                # launches the Dash replay app on a trade log
└── new-strategy.md          # scaffolds a new strategy file + config + test
```

Each command file follows this format:

```markdown
---
description: Brief description shown in the slash command picker
---

The body of the command — instructions to Claude on what to do when this
command is invoked. This can be a multi-step procedure, a template to fill
in, or a reference to a script to run.
```

The commands are added incrementally as the workflows they automate become real. Don't write all of them up front; write each one when you find yourself doing the same workflow twice.

## Conventions

**Naming:**

- Modules and packages: `snake_case`
- Classes: `PascalCase`
- Functions, variables, methods: `snake_case`
- Constants: `SCREAMING_SNAKE_CASE`
- Private (module-internal): leading underscore `_helper`
- Strategy files: `<symbol>_<style>_<version>.py`, e.g. `zn_macd_rev_v1.py`
- Strategy configs: same base name, `.yaml` extension
- Test files: `test_<module>.py`

**Imports:**

- Absolute imports always (`from trading_research.data.schema import ...`), never relative.
- Standard library, then third party, then first party. Ruff's import sorter handles this automatically.
- No `from module import *` ever.

**Type hints:**

- Required on all public functions in `src/`.
- Required on all functions in `data/`, `backtest/`, and `risk/` (the strict pyright zones).
- Optional on private helpers and on test code.

**Docstrings:**

- Required on all public functions and classes in `src/`.
- Google or NumPy format, consistent within a module.
- Don't document the obvious. Document the *why*, the *gotchas*, the *invariants*.

**Error handling:**

- Raise specific exceptions, not bare `Exception`.
- Custom exception types live in the module they're raised from, named like `<Action>Error` (e.g. `ValidationError`, `IngestError`).
- Never silently swallow exceptions. Log and re-raise, or log and return a sentinel value with a clear name.

**Logging:**

- `from trading_research.utils.logging import get_logger; logger = get_logger(__name__)`
- Log levels: `debug` for development, `info` for normal events, `warning` for unexpected-but-handled, `error` for failures, `critical` for state-corrupting failures.
- Structured logging: `logger.info("backtest_complete", run_id=run_id, trades=len(trades), pnl=total_pnl)` not `logger.info(f"Backtest complete: {len(trades)} trades, ${total_pnl}")`.
- Never log secrets. Never log full bar datasets (too big). Log identifiers and counts.

**Tests:**

- Every function in a strict-typed module has at least one test.
- Tests live in `tests/` mirroring `src/` structure.
- Fixtures use small, hand-crafted parquet files in `tests/fixtures/`, not generated data.
- Mark slow tests with `@pytest.mark.slow` and exclude them from default runs: `uv run pytest -m "not slow"`.

## Initial scaffolding procedure

When this skill is invoked for the first time on an empty `C:\trading-research\` directory, the agent performs this sequence:

1. **Verify `uv` is installed.** If not, install it. Confirm with `uv --version`.
2. **Initialize the project.** Create `pyproject.toml` and `.python-version` from the templates above.
3. **Create the directory tree.** All of the directories shown in the layout section, with `.gitkeep` files where needed.
4. **Write `.gitignore`, `.ruff.toml`, and the `pyproject.toml` tool sections.**
5. **Run `uv sync`** to create the virtual environment and install dependencies.
6. **Initialize git.** `git init`, then `git add .` and `git commit -m "Initial scaffold"`.
7. **Verify the install.** Run `uv run python -c "import trading_research"` to confirm the package is importable, and `uv run pytest` to confirm pytest works (it'll find no tests, that's fine).
8. **Report what was created** to the human in a short summary, with the next concrete action they can take (typically: "ready to set up `.env` with your TradeStation credentials").

This entire procedure is done by the agent. The human is not asked to copy-paste commands. The only human involvement is approving any prompt from `uv` that would modify their system Python.

## Standing rules this skill enforces

1. **No code outside `src/trading_research/`.** Scripts go in `scripts/`, tests in `tests/`, exploration in `notebooks/`. Library code lives in the package.
2. **No hard-coded paths.** Use `pathlib.Path` and resolve relative to the project root. The project root is found via a helper in `utils/`.
3. **No `print()` in `src/`.** Use `structlog`. Print is for CLI scripts and notebooks only.
4. **No string paths in source code.** `Path("data/clean")`, not `"data\\clean"` or `"data/clean"`.
5. **No notebook code in version control.** Notebooks are gitignored. Promotion to `src/` is the path from exploration to production.
6. **`uv.lock` is committed and authoritative.** Don't run `pip install` directly. All dependency changes go through `uv add` or `uv remove`, which update both `pyproject.toml` and `uv.lock`.
7. **Configs are YAML, code is Python.** A strategy parameter that lives in a Python file is a bug.

## When to invoke this skill

Load this skill when the task involves:

- Setting up the project on a new machine (initial scaffolding)
- Adding a new top-level module, package, or directory
- Configuring tooling (ruff, pytest, pyright, structlog)
- Deciding where a new file or feature belongs in the layout
- Modifying `pyproject.toml`, `.gitignore`, or environment setup
- Adding a new slash command

Don't load this skill for routine implementation work in an existing module — the conventions are already encoded in the existing files at that point. Load it when you're making a structural change.

## Open questions for build time

1. **Do we want a `Makefile` or `justfile`** for common commands (`make test`, `make backtest`), or are `uv run` invocations enough? Recommend `justfile` if cross-platform matters; skip if not.
2. **Pre-commit hooks** for ruff and pytest? They catch bugs before commit but slow down the commit cycle. Recommend yes for ruff (fast), optional for pytest (slow).
3. **Documentation site** with mkdocs or similar? Probably overkill for a personal project. The skill files and `CLAUDE.md` are the documentation.
