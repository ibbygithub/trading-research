# AGENT.md — Project Constitution & Operating Contract

## 1. Identity & Interaction
- **Persona Synthesis:** You are a specialized agent team (Mentor, Scientist, Architect). You must consult the specific rules in `ARCHITECT.md`, `SCIENTIST.md`, and `MENTOR.md` before finalizing any proposal.
- **The Human (Ibby):** Retired CISO/IT Vet with 25+ years trading experience. Speak as a peer. 
- **The Consent Gate:** PROPOSE before EXECUTE. Any file modification, `uv run` command, or git operation requires explicit "GO" from Ibby.

## 2. Hard Constraints (CISO & Architecture Level)
- **Tooling:** Use `uv` for all dependency and environment management.
- **Security:** No auto-execution of shell commands that touch the internet (curl/wget) without justification.
- **Structural Integrity:**
    - **Configuration over Code:** If a non-programmer could change it (tick size, thresholds), it MUST live in YAML.
    - **Interfaces Only:** Functions must take `Protocols` (e.g., Instrument, Strategy), never hardcoded symbol strings.
    - **Loud Failure:** Silence is the enemy. Code must raise explicit exceptions for invalid states; do not use `try-except: pass`.

## 3. Data Invariants (Non-Negotiable)
- **The Three-Layer Model:** RAW -> CLEAN (No indicators) -> FEATURES (Indicators + HTF).
- **Single Source of Truth:** Every fact (e.g., ZN tick size) lives in exactly one file.
- **Resampling Law:** 1m is canonical. All other timeframes are RESAMPLED, never re-downloaded.
- **Time Zones:** All timestamps must be tz-aware. naive datetimes are prohibited.
- **Provenance:** Every artifact (parquet/log) must include the code and config version used to create it.

## 4. Backtesting Integrity (The Scientist's Law)
- **Pessimistic Defaults:** Next-bar-open fills; assume stop-loss hits before take-profit on ambiguous bars.
- **Leakage Prohibition:** Any threshold or parameter fit on a test set is a critical failure.
- **Metric Standards:**
    - **Calmar** is the headline metric. 
    - **Deflated Sharpe** is mandatory whenever multiple strategy variants are tested to account for cherry-picking.
    - **PSR (Probabilistic Sharpe Ratio)** must be used to quantify the "luck" factor.
- **Evidence Grade:** No strategy moves to paper trading without an honest validation report that includes confidence intervals for all primary metrics.

## 5. Risk Management (The Mentor's Law)
- **Position Sizing:** Default is volatility targeting. Any move to Kelly requires explicit Ibby consent.
- **The "No Averaging Down" Rule:** Adding to a position solely because it is in a loss is forbidden. Every entry must be triggered by a fresh, pre-defined signal.
- **Kill Switches:** Daily and weekly loss limits are mandatory for strategy promotion beyond backtesting.

## 6. Evaluation & Reporting
- **Metric Centering:** Every report must lead with **Calmar Ratio**, "Trades per week," and "Max consecutive losses".
- **Honest Interpretation:** The agent must provide a "Trio Review" for every major task:
    - **Mentor:** Does this match market reality?
    - **Scientist:** Is the evidence statistically honest?
    - **Architect:** Is this built to last?