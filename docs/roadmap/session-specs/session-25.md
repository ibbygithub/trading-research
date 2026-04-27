# Session 25 — Pipeline Refactor Against Instrument Protocol

**Agent fit:** either (Gemini-eligible with close spec adherence)
**Estimated effort:** L (4h+)
**Depends on:** 23-a
**Unblocks:** 28, B1, 29

## Goal

Replace all hardcoded `"ZN"` strings and symbol-specific logic in the data pipeline with calls to `InstrumentRegistry.get(symbol)`, resolving OI-010, OI-011, and OI-012, so the pipeline can process any instrument in the registry without code changes.

## Context

Three hardcoded ZN references exist in the data pipeline (from `status-report-session-22.md`):

- **OI-010** — RTH window hardcoded for ZN in `validate.py`
- **OI-011** — Hardcoded `"ZN"` in `continuous.py` output paths
- **OI-012** — `last_trading_day_zn()` misleading name in `validate.py`

Session 23-a provides the `Instrument` model that makes these fixable. This session is mechanical refactoring: find the hardcoded values, replace with Instrument field lookups, verify existing ZN tests still pass, add 6E smoke tests to prove generalization.

## In scope

Modify these files (locate via grep for `"ZN"` and `zn_`):

- `src/trading_research/data/validate.py`:
  - Replace `last_trading_day_zn()` with `last_trading_day(instrument: Instrument)`. Update signature at all call sites.
  - Replace hardcoded RTH window with `instrument.rth_open_et` and `instrument.rth_close_et`.
  - Calendar name comes from `instrument.calendar_name`, not a local constant.
- `src/trading_research/data/continuous.py`:
  - Replace hardcoded `"ZN"` in output paths with `instrument.symbol`.
  - Replace any `data/clean/ZN_*.parquet` patterns with parameterized paths.
- Any other file where `grep -r '"ZN"' src/` finds a match that is not a legitimate constant (e.g. not the ZN-specific strategy file which has been shelved).
- Existing CLI commands that take `--symbol`: verify they pass the Instrument object (not the symbol string) to downstream functions.

Add these tests:

- `tests/data/test_validate_generalized.py`:
  - `test_last_trading_day_zn` — same as old test, but now calls `last_trading_day(registry.get("ZN"))`.
  - `test_last_trading_day_6e` — same function with 6E Instrument, returns a valid date (a recent known 6E trading day).
  - `test_rth_window_zn` — ZN Instrument's RTH is 08:20–15:00.
  - `test_rth_window_6e` — 6E Instrument's RTH window applies correctly.
- `tests/data/test_continuous_generalized.py`:
  - `test_continuous_output_path_zn` — path contains "ZN".
  - `test_continuous_output_path_6e` — path contains "6E", does NOT contain "ZN".
  - `test_continuous_smoke_6e` — can invoke the continuous-series builder with a 6E Instrument and get a valid-shape output (can use mocked data; full data pipeline is session 28).

Verify by grep that no `"ZN"` literals remain outside:
- `configs/instruments.yaml` (allowed — this is the registry)
- `configs/strategies/zn-macd-pullback-v1.yaml` (allowed — shelved strategy)
- `src/trading_research/strategies/zn_macd_pullback.py` (allowed — shelved, frozen)
- Test files named `test_*zn*.py` (allowed)
- Historical session logs, handoff docs, memory files (allowed — documentation)

## Out of scope

- Do NOT refactor strategy code. ZN v1 and v2 strategy files stay as-is (shelved reference).
- Do NOT add a new instrument (6E) to the full data pipeline run — that's session 28.
- Do NOT change the Instrument model or registry — that's 23-a and is frozen.
- Do NOT touch the trial registry or stationarity code — those are 24 and 26.
- Do NOT change the base-v1 featureset contents — codifying is 23-a, no extension here.

## Acceptance tests

- [ ] `grep -rn '"ZN"' src/trading_research/ --include='*.py' | grep -v 'zn_macd_pullback.py'` returns zero lines.
- [ ] `grep -rn 'last_trading_day_zn' src/trading_research/` returns zero lines.
- [ ] `uv run pytest tests/data/` passes with all existing tests green and the new generalized tests green.
- [ ] `uv run pytest` — full suite passes (all 401+ tests).
- [ ] A dry-run of the validation pipeline on ZN still produces the same validated output as before (no regression).
- [ ] `ruff check src/trading_research/data/ tests/data/` passes.

## Definition of done

- [ ] Grep-based smoke checks above all pass.
- [ ] Work log includes a list of every file modified and the specific lines that changed.
- [ ] Work log lists any call sites that were updated (so reviewers can spot-check).
- [ ] Committed on feature branch `session-25-pipeline-refactor`.

## Persona review

- **Architect: required.** Reviews that Instrument is being used idiomatically (passed as object, not re-looked-up), no regressions in module coupling.
- **Data scientist: optional.** Reviews that calendar and RTH changes don't alter validation semantics for ZN (the old ZN validation must still behave identically).
- **Mentor: optional.**

## Design notes

### Prefer passing the Instrument object, not the symbol

Bad:
```python
def process_bars(symbol: str, bars: pd.DataFrame) -> pd.DataFrame:
    instrument = InstrumentRegistry().get(symbol)  # lookup every call
    ...
```

Good:
```python
def process_bars(instrument: Instrument, bars: pd.DataFrame) -> pd.DataFrame:
    ...
```

If the CLI takes `--symbol`, look it up once at the CLI boundary and pass the Instrument object down.

### Keep ZN behavior byte-identical

The refactor must not change the validated output for ZN. If the old code had a subtle ZN-specific behavior that the generalized version accidentally drops, that's a regression. Before-and-after validation is worth doing: run the pipeline on one day of ZN data before the refactor, run it after, diff the outputs. They should be identical.

### `last_trading_day` signature

```python
def last_trading_day(instrument: Instrument, reference_date: date | None = None) -> date:
    """Return the last calendar-recognized trading day at or before reference_date."""
    calendar = get_calendar(instrument.calendar_name)
    ...
```

## Risks

- **Hidden hardcodings in tests.** Test fixtures may assume ZN's RTH window is 08:20–15:00 as a magic constant. Update tests to fetch from registry, not hardcode.
- **Path format changes break downstream readers.** If a script expects `data/clean/ZN_1m_*.parquet`, changing to `data/clean/{instrument.symbol}_1m_*.parquet` must produce the same pattern for ZN. Verify.
- **Gemini running this session.** If Gemini is the agent, include explicit "run `uv run pytest` after each file edit" instruction to catch regressions early. Statistical code is Claude's lane; this refactor is straightforward enough for Gemini with clean acceptance tests.

## Reference

- Open issues OI-010, OI-011, OI-012 in `docs/handoff/status-report-session-22.md`.
- Session 23-a spec for Instrument model shape.
- `.claude/rules/platform-architect.md` — especially "When we add the fifth instrument, does this file change or not?" (no, after this session).

## Success signal

`python -c "from trading_research.data.validate import last_trading_day; from trading_research.core import InstrumentRegistry; print(last_trading_day(InstrumentRegistry().get('6E')))"` prints a recent trading day for 6E without error. The same command with ZN still works. That's generalization proven.
