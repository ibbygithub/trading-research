# Session 24 — Trial Registry Versioning + Stationarity Suite Design

**Agent fit:** claude
**Estimated effort:** M (2–4h)
**Depends on:** 23-a
**Unblocks:** 26, 27, 29

## Goal

Fix the trial registry so every entry carries a code-version hash (retroactively tagging v1 and v2 trials as a pre-hardening cohort), and design — but do not yet implement — the stationarity suite (ADF, Hurst, OU half-life) as a spec the implementation session (26) will execute against.

## Context

The `runs/.trials.json` registry currently logs strategy variants and computes Deflated Sharpe across them. DSR assumes iid trials from a stable procedure. The backtest engine has evolved across sessions (kurtosis fix in session 17, meta-labeling in 18, path changes in 20), so current trials are not iid — comparing v1 DSR to v2 DSR is apples-to-oranges.

The fix is cohort-versioning, not registry reset. Each trial gets tagged with the git SHA of the backtest engine code at the time it was run. DSR is computed within a cohort. Ibby confirmed this approach in the planning session.

The stationarity suite (ADF, Hurst, OU half-life) is PLANNED but not designed. This session specifies what it will test, on which series, with what thresholds, and how it integrates with the FEATURES layer. Session 26 implements against this spec.

## In scope

**Trial registry changes** — code under `src/trading_research/eval/` or wherever the registry lives (locate via `runs/.trials.json` producer):

- Add `code_version: str` field to the trial entry schema (short git SHA at time of run).
- Add `featureset_hash: str` field (from `FeatureSet.compute_hash()` when applicable).
- Add `cohort_label: str` field — free-form label, defaults to the code_version.
- Migration script: read `runs/.trials.json`, tag every existing entry with `code_version: "pre-hardening"` and `cohort_label: "pre-hardening"`. Round-trip test that migration is idempotent.
- DSR computation function updated to group trials by `cohort_label` and compute DSR per cohort. Cross-cohort DSR is explicitly disabled (returns None with a logged warning).
- Update any reporting code that reads the registry to display cohort information.

**Stationarity suite DESIGN only** — a new document `docs/design/stationarity-suite.md`:

- Which series get tested: per-instrument, per-timeframe, list is specified.
- Tests to run: ADF (Augmented Dickey-Fuller), Hurst exponent, Ornstein-Uhlenbeck half-life.
- Thresholds: what counts as "stationary," "mean-reverting," "trending," "noisy." Cite Lopez de Prado or other source.
- Integration: results stored as part of FEATURES layer manifest, or as a separate `stationarity/` artifact? Decision documented.
- Output: what the report looks like — CSV? JSON? Section in the HTML backtest report?
- Interaction with strategy selection: session 29 uses this output to pick mean-reversion vs trend-following vs noise-filter strategy class.
- Dependencies: `statsmodels` for ADF, `hurst` or custom implementation, `scipy.optimize` for OU fit.

Create under `tests/eval/`:

- `test_trial_registry_versioning.py`:
  - `test_new_trial_has_code_version` — new trial has the field populated.
  - `test_migration_idempotent` — running migration twice produces same result.
  - `test_dsr_within_cohort` — DSR computed within a single cohort returns a number.
  - `test_dsr_across_cohorts_returns_none` — DSR requested across cohorts returns None + warning.

## Out of scope

- Do NOT implement ADF, Hurst, or OU code. That's session 26.
- Do NOT run the stationarity suite on any instrument data. That's session 28.
- Do NOT change the backtest engine. Only the trial registry and DSR function.
- Do NOT touch the manifest format for CLEAN or FEATURES parquets. That's session 25 if at all.

## Acceptance tests

- [ ] `uv run pytest tests/eval/test_trial_registry_versioning.py -v` passes.
- [ ] `uv run pytest` — full suite passes.
- [ ] `runs/.trials.json` file has been migrated: every existing entry has `code_version: "pre-hardening"` and `cohort_label: "pre-hardening"`. Verified by script or manual inspection.
- [ ] `docs/design/stationarity-suite.md` exists and is complete — every section listed in the "In scope" specification is present.
- [ ] A new trial run (you can simulate by manually adding an entry via the registry API) gets a current git SHA as `code_version`, different from "pre-hardening".
- [ ] DSR function returns a number for a cohort, None (with warning) when called across cohorts.

## Definition of done

- [ ] Migration has been run against `runs/.trials.json` and the file is committed with its new schema.
- [ ] Stationarity suite design doc is thorough enough that session 26 can implement from it without further design decisions.
- [ ] Work log at `outputs/work-log/YYYY-MM-DD-session-24.md`.
- [ ] Committed on feature branch `session-24-registry-versioning`.

## Persona review

- **Data scientist: required.** Reviews the DSR cohort logic — the math must be right. Reviews the stationarity suite design doc before merge — thresholds, tests, interpretation. This is their session to drive.
- **Architect: required.** Reviews registry schema change, migration pattern, how `featureset_hash` integrates with `FeatureSet` from 23-a.
- **Mentor: optional.** No market logic but may weigh in on thresholds (e.g., "a Hurst of 0.55 is not meaningfully trending").

## Design notes

### Schema migration pattern

Read the existing JSON, apply transformations, write back with backup. Example:

```python
def migrate_trials(path: Path, backup: bool = True) -> None:
    data = json.loads(path.read_text())
    if backup:
        backup_path = path.with_suffix(".json.backup")
        backup_path.write_text(path.read_text())
    for trial in data.get("trials", []):
        trial.setdefault("code_version", "pre-hardening")
        trial.setdefault("cohort_label", "pre-hardening")
        trial.setdefault("featureset_hash", None)
    path.write_text(json.dumps(data, indent=2, sort_keys=True))
```

Round-trip test: run migration twice; output is identical to first run.

### DSR cross-cohort disabled

```python
def compute_dsr(trials: list[Trial], cohort: str | None = None) -> float | None:
    if cohort is None:
        logger.warning("DSR requested without cohort; use per-cohort DSR. Returning None.")
        return None
    filtered = [t for t in trials if t.cohort_label == cohort]
    if len(filtered) < MIN_TRIALS_FOR_DSR:
        logger.warning(f"Cohort {cohort} has {len(filtered)} trials; DSR needs >= {MIN_TRIALS_FOR_DSR}")
        return None
    return _compute_dsr(filtered)
```

### Stationarity suite design doc structure

The design doc `docs/design/stationarity-suite.md` must have these sections:

1. **Purpose** — what the suite tests and why.
2. **Tests** — ADF (with lag selection method), Hurst (rescaled-range method), OU half-life (via least-squares fit).
3. **Input series** — for each instrument: returns (1m, 5m, 15m), VWAP-spread, log-prices.
4. **Thresholds** — "stationary" = ADF p < 0.05; "persistent/trending" = Hurst > 0.55; "mean-reverting" = Hurst < 0.45 AND OU half-life < N bars.
5. **Output format** — pandas DataFrame with columns `instrument, timeframe, series_name, test_name, statistic, p_value, interpretation`.
6. **Integration** — how the FEATURES layer triggers a stationarity report build. Probably a separate CLI command `stationarity --symbol 6E` rather than on every feature build (it's expensive).
7. **Consumers** — session 29's strategy-class decision reads this output.
8. **Validation** — how we verify our implementation against a reference (statsmodels for ADF).

### Why no implementation this session

Splitting design from implementation for statistical code is valuable: the design doc is reviewed by the data scientist separately from the implementation, which catches "wrong test" errors before they're expensive to fix. Implementation session 26 is purely mechanical once the design is right.

## Risks

- **Migration overwrites data.** Mitigation: backup file created on first migration. Commit the backup.
- **Stationarity thresholds chosen wrong.** Mitigation: design doc explicitly cites sources for thresholds. Data scientist review catches unjustified thresholds.
- **Registry schema change breaks existing readers.** Mitigation: all fields added have defaults, so old reader code still works (it just ignores the new fields).

## Reference

- `runs/.trials.json` — the registry file being migrated.
- `src/trading_research/eval/` — probable location of DSR computation.
- `docs/handoff/status-report-session-22.md` — context on DSR cohort issue.
- Lopez de Prado, *Advances in Financial Machine Learning*, ch. 17 on fractional differentiation and stationarity.
- statsmodels `adfuller` docs — reference implementation.

## Success signal

Running `uv run python -c "from trading_research.eval import load_trials, compute_dsr; t = load_trials(); print(compute_dsr(t, cohort='pre-hardening'))"` prints a number. Running the same with `cohort=None` prints None and logs a warning. The design doc is readable end-to-end by the data scientist without follow-up questions.
