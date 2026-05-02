# Session 29 — Strategy Foundation & Coupling Fixes

**Status:** Spec — ready to execute
**Effort:** 2 calendar days, four sub-sprints (M+M+M+M)
**Depends on:** Track A complete (session 28); plan v2 approved
**Unblocks:** sprint 30 (6E backtest v1), sprint D1 (loss limits)
**Personas required:** Architect (29a), Data Scientist (29a), Mentor (29a)

This spec follows `outputs/planning/multi-model-handoff-protocol.md`. The
spec→test→impl ordering is non-negotiable. Sub-sprints 29b–d implement
against tests authored in 29a.

---

## Goal

End state at the close of sprint 29:

1. `vwap-reversion-v1` is a registered template; `walkforward.py` instantiates
   strategies via `TemplateRegistry`, not via dynamic-import strings. Two
   strategy systems collapse to one (architect's Option A staged).
2. `BacktestEngine` calls `Strategy.size_position(...)` for every entry;
   `BacktestConfig.quantity` is fallback only.
3. Tradeable OU half-life bounds live in `configs/instruments.yaml`,
   per-instrument; `stats/stationarity.py` reads from `Instrument`.
4. Naming convention for templates and strategy instances is documented and
   enforced.
5. Mulligan freshness invariant is documented at the Strategy Protocol level.
6. ZN existing classifications are unchanged (regression test).
7. 6E re-classifies as TRADEABLE under per-instrument bounds.

---

## Architectural decisions to be ratified in 29a

The following decisions are required as inputs. 29a's deliverable is the
written ratification (committed to this spec as an addendum).

### Decision 29-D1 — Walkforward / Registry coupling
**Recommendation:** Option A staged.
- Sprint 29b: walkforward learns to consume a `template:` field in YAML
  configs. If `template:` is present, instantiate via `TemplateRegistry.get(...)`
  and call `strategy.generate_signals(bars, features, instrument)`. If
  `signal_module:` is present, fall back to current dynamic-import path.
- Sprint 30: 6E config uses `template: vwap-reversion-v1`.
- Sprints F1/F2: ZN strategies retrofitted as templates `zn-vwap-reversion-v0`
  and `zn-macd-pullback-v0`; dynamic-import path deprecated with a warning.
- Sprint 38: dynamic-import path removed.

### Decision 29-D2 — OU bounds location
**Recommendation:** in `Instrument`, at field `tradeable_ou_bounds_bars`,
mapping timeframe → `(lower, upper)`. Default fallback (used when an
instrument does not declare bounds) lives in `core/instruments.py`'s
`Instrument` model as a class-level default that matches the *current* ZN
values, so existing ZN behaviour is preserved.

```yaml
# configs/instruments.yaml — 6E entry adds:
6E:
  ...
  tradeable_ou_bounds_bars:
    1m: [10, 240]      # 10 min to 4 hr
    5m: [10, 80]       # 50 min to ~6.7 hr
    15m: [4, 30]       # 1 hr to ~7.5 hr
```

### Decision 29-D3 — Naming convention
- Templates: `<strategy-class>-v<N>` (kebab-case). Examples: `vwap-reversion-v1`,
  `macd-pullback-v1`. Version bumps when knob schema or signal logic changes
  in a way that breaks back-compat.
- Strategy *instances*: `<template>-<instrument>-<config-hash-short>`.
  Example: `vwap-reversion-v1-6E-a3f5b1`. The short hash is the first 6 hex
  chars of `blake2b(yaml.dump(knobs)).hexdigest()`.
- Existing ZN modules become `zn-vwap-reversion-v0` and `zn-macd-pullback-v0`
  on retrofit. Old YAML configs continue to work via fallback.

### Decision 29-D4 — Mulligan freshness invariant
Documented in `core/strategies.py` at the `Strategy.exit_rules` docstring:

> When `exit_rules` returns `ExitDecision(action="scale_in", ...)`, the engine
> requires that a *new* `Signal` was emitted by `generate_signals` for the
> position's direction at a strictly later timestamp than the original entry's
> trigger signal. Returning `scale_in` without a fresh emission is a Protocol
> violation and the engine will reject the action with a `MulliganViolation`
> exception. This rule exists to prevent adverse-P&L "averaging-down" from
> being implemented as a Mulligan re-entry.

This is enforced in sprint 32 with contract tests; the docstring lands now.

---

## Sub-sprints

### 29a — Architectural ratification + spec & stub-test authoring
**Model:** Opus 4.7 | **Effort:** M (~2 hr)

**Inputs:**
- This document
- All three persona reviews under `outputs/planning/peer-reviews/`
- Code: `core/strategies.py`, `core/templates.py`, `core/instruments.py`,
  `backtest/engine.py`, `backtest/walkforward.py`, `stats/stationarity.py`

**Outputs:**
- This document amended with ratification of decisions 29-D1 through 29-D4
  (or with a documented alternative + reasoning).
- Stub test files (committed, all tests `xfail` or `skip` with reason):
  - `tests/contracts/test_walkforward_uses_registry.py`
  - `tests/contracts/test_engine_uses_size_position.py`
  - `tests/contracts/test_ou_bounds_from_instrument.py`
  - `tests/contracts/test_strategy_naming_convention.py`
- Strategy Protocol docstring updated with Mulligan freshness invariant.
- Work log entry recording each ratified decision with reasoning.

**Acceptance:** stub tests run (skipping); decisions are committed; sub-sprints
29b–d have a written contract.

**No code that ships behaviour. Only spec, decisions, and stubs.**

---

### 29b — Walkforward retrofit + `vwap-reversion-v1` template
**Model:** Sonnet 4.6 | **Effort:** M (~3 hr)

**Inputs:**
- Spec (this doc, post-29a)
- Stub test `tests/contracts/test_walkforward_uses_registry.py`
- 6E recommendation doc

**Outputs:**
- `src/trading_research/strategies/vwap_reversion_v1.py` — implements the
  Strategy Protocol. Class `VWAPReversionV1` with knob model:

```python
class VWAPReversionV1Knobs(BaseModel):
    entry_threshold_atr: float = Field(2.2, ge=1.0, le=4.0)
    exit_target_atr: float = Field(0.3, ge=0.0, le=1.5)
    stop_loss_atr: float = Field(2.5, ge=1.0, le=5.0)
    max_hold_bars: int = Field(60, ge=1, le=240)
    entry_window_start_utc: time = time(12, 0)
    entry_window_end_utc: time = time(17, 0)
    entry_blackout_minutes_after_session_open: int = Field(60, ge=0, le=240)
    flatten_offset_minutes_before_settlement: int = Field(0, ge=0, le=60)
    blackout_minutes_before_release: int = Field(30, ge=0, le=120)
    feature_set: str = "base-v1"

@register_template(
    name="vwap-reversion-v1",
    human_description="Intraday VWAP mean reversion with extended hold window.",
    knobs_model=VWAPReversionV1Knobs,
    supported_instruments=["6E"],
    supported_timeframes=["5m", "15m"],
)
class VWAPReversionV1:
    ...
```

  - `generate_signals`: enters when `vwap_spread / atr` exceeds
    `entry_threshold_atr`, only within the entry window AND outside the
    after-open blackout AND outside any release blackout.
  - `size_position`: vol-targeting (CLAUDE.md default) using
    `instrument.contract_multiplier` and `context.account_equity`.
  - `exit_rules`: take profit at `exit_target_atr` band, stop at
    `stop_loss_atr`, max hold at `max_hold_bars`, hard flatten at
    instrument settlement minus `flatten_offset_minutes_before_settlement`.
- `src/trading_research/backtest/walkforward.py` retrofit:
  - Read `template:` from YAML; if present, `strategy = registry.get(template).instantiate(knobs)`.
  - Call `strategy.generate_signals(bars, features, instrument)`.
  - Maintain backward-compat for `signal_module:` configs (legacy ZN).
- `configs/strategies/6e-vwap-reversion-v1.yaml`:

```yaml
strategy_id: vwap-reversion-v1-6E-{config-hash-short}
template: vwap-reversion-v1
symbol: 6E
timeframe: 5m
feature_set: base-v1
knobs:
  entry_threshold_atr: 2.2
  exit_target_atr: 0.3
  stop_loss_atr: 2.5
  max_hold_bars: 60
  entry_window_start_utc: "12:00:00"
  entry_window_end_utc: "17:00:00"
  entry_blackout_minutes_after_session_open: 60
  flatten_offset_minutes_before_settlement: 0
  blackout_minutes_before_release: 30
backtest:
  fill_model: next_bar_open
  start_date: "2018-01-01"
  end_date: "2024-12-31"
```

**Acceptance:**
- `tests/contracts/test_walkforward_uses_registry.py` passes (no skip).
- `tests/strategies/test_vwap_reversion_v1.py` passes — verifies that:
  - `generate_signals` returns no signals before the entry window.
  - Signals respect the after-open blackout.
  - Signal direction matches sign of vwap_spread overshoot.
  - All signals carry `metadata["regime"]` and `metadata["vwap_spread_z"]`.
- Existing ZN tests still pass (backward compatibility).

---

### 29c — `Strategy.size_position` wired into engine
**Model:** Sonnet 4.6 | **Effort:** M (~3 hr)

**Inputs:**
- Spec (this doc)
- Stub test `tests/contracts/test_engine_uses_size_position.py`

**Outputs:**
- `src/trading_research/backtest/engine.py`:
  - Engine now requires a `Strategy` (or compatible) on construction.
  - Order construction calls `strategy.size_position(signal, context, instrument)`
    where `context: PortfolioContext` is built from current engine state.
  - If the returned size is 0, the trade is suppressed (logged).
  - `BacktestConfig.quantity` is now an optional fallback used only when no
    Strategy is provided (legacy path for existing ZN tests).
- `tests/contracts/test_engine_uses_size_position.py`:
  - Construct a synthetic Strategy whose `size_position` returns a deterministic
    integer; assert engine uses that integer for the trade size.
  - Construct one whose `size_position` returns 0; assert the trade is suppressed.
  - Construct one that raises; assert the engine surfaces the error rather
    than silently using `quantity`.
- Migration note in work log: existing ZN tests keep using `quantity` via
  fallback; F1 retrofit will convert them.

**Acceptance:** stub test passes; existing tests unchanged; engine can run
with either path.

---

### 29d — OU bounds migration to instrument registry (Gemini)
**Model:** Gemini 3.1 (Antigravity) | **Effort:** M (~2 hr)

This sub-sprint follows `outputs/planning/gemini-validation-playbook.md`.

**Inputs:**
- Spec (this doc; decisions 29-D2)
- Stub test `tests/contracts/test_ou_bounds_from_instrument.py` (pre-written)
- `outputs/planning/gemini-validation-playbook.md`

**Outputs:**
- `src/trading_research/core/instruments.py`:
  - Add field `tradeable_ou_bounds_bars: dict[str, tuple[float, float]]` to
    `Instrument` Pydantic model with default factory matching current ZN values.
- `configs/instruments.yaml`:
  - 6E entry gains `tradeable_ou_bounds_bars` with values from decision 29-D2.
  - ZN entry explicitly gains the same field with current ZN values
    (no change in classification).
- `src/trading_research/stats/stationarity.py`:
  - Module-level `_OU_TRADEABLE` constant deleted.
  - `compute_stationarity` (or whichever function consumes the bounds) takes
    the `Instrument` and reads from `instrument.tradeable_ou_bounds_bars`.
- `tests/contracts/test_ou_bounds_from_instrument.py`:
  - Pre-written assertion: passing 6E + 5m bounds yields TRADEABLE for the
    OU half-life observed in session 28 (~33 bars).
  - Pre-written assertion: passing ZN + 5m yields the same classification
    that was observed pre-migration on the existing ZN report.
- `tests/stats/test_ou_canonical_parity.py` (NEW, per playbook Example C):
  - Parity test against `statsmodels.api.OLS` for OU half-life calculation.
  - rtol=1e-9, atol=1e-12.
  - SEED=20260426; N=5000.

**Validation rules (from playbook):**
- Canonical reference: `statsmodels.api.OLS` for the OU regression.
- Parity test fixture: `tests/stats/test_ou_canonical_parity.py` (Sonnet
  pre-writes the fixture in 29a; Gemini fills implementation in 29d).
- Tolerance: rtol=1e-9, atol=1e-12.
- Escalation contact: 29a spec author.

**Things Gemini must NOT do:**
- Author its own validation tests against the canonical (use Sonnet's stub).
- Loosen tolerances.
- Change ZN bounds (that would change ZN classifications).
- Change the call signature of `compute_stationarity` beyond adding the
  Instrument parameter.

**Acceptance:**
- All four contract test files (29a stubs) now pass with real implementations.
- `tests/stats/test_ou_canonical_parity.py` passes.
- Existing ZN stationarity report regenerated; classifications IDENTICAL
  to pre-migration (regression check).
- 6E classifies as TRADEABLE under new bounds.

---

## Cross-cutting acceptance (sprint 29 done)

A clean run of the following is the gate. If any fails, the sprint is not done:

```
uv run pytest tests/                               # Full suite green
uv run pytest tests/contracts/                     # All contract tests pass
uv run trading-research describe-template vwap-reversion-v1   # Lists knobs + ranges
uv run trading-research stationarity --symbol 6E   # 6E reclassifies TRADEABLE
uv run trading-research stationarity --symbol ZN   # ZN classifications IDENTICAL
```

## Definition of done checklist

- [ ] 29a decisions ratified and committed.
- [ ] Four contract test files written as stubs by 29a, passing as real tests by end of 29d.
- [ ] `vwap-reversion-v1` registered, instantiable, callable through walkforward.
- [ ] `Strategy.size_position` reachable from engine; old `quantity` path is fallback only.
- [ ] OU bounds in instrument registry; ZN classifications unchanged; 6E TRADEABLE.
- [ ] Strategy Protocol docstring includes Mulligan freshness invariant.
- [ ] Work log per CLAUDE.md convention.
- [ ] Branch `session-29-strategy-foundation`; no merge to `develop` without architect + data-scientist signoff.

## Decision Ratifications (29a)

**Ratified:** 2026-05-01, session 29a execution

### 29-D1 — Walkforward / Registry coupling: RATIFIED as Option A staged

Rationale: The existing `signal_module:` path in walkforward.py works for ZN and
must continue to work untouched. Adding `template:` as a parallel path lets us
adopt TemplateRegistry for new strategies (starting with 6E) without breaking
any existing ZN config or test. The staging plan (29b → 30 → F1/F2 → 38) provides
a clean migration runway. The `signal_module:` fallback remains until sprint 38.

### 29-D2 — OU bounds location: RATIFIED as per-instrument field

Rationale: OU tradeable half-life bounds are instrument-specific — ZN and 6E have
fundamentally different reversion speeds due to different market microstructure
(rate-event-driven vs. rate-differential-driven). Storing bounds in
`Instrument.tradeable_ou_bounds_bars` as `dict[str, tuple[float, float]]` keeps
the single-source-of-truth principle: the instrument registry already owns tick
size, session hours, and margin — OU bounds belong there too. The class-level
default on the Instrument model preserves current ZN behaviour for any instrument
that does not explicitly declare bounds.

### 29-D3 — Naming convention: RATIFIED as specified

Rationale: Templates use `<strategy-class>-v<N>` (kebab-case). Instances use
`<template>-<instrument>-<config-hash-short>`. The blake2b short hash (6 hex
chars) ensures uniqueness across knob configurations without manual naming.
Existing ZN modules become `zn-vwap-reversion-v0` and `zn-macd-pullback-v0` on
retrofit (sprints F1/F2), preserving the version history.

### 29-D4 — Mulligan freshness invariant: RATIFIED as specified

Rationale: The docstring is now committed on the `Strategy.exit_rules` method.
Contract tests enforcing the invariant at the engine level will land in sprint 32.
The invariant prevents the most dangerous failure mode in mean-reversion
strategies: averaging down disguised as a scale-in.

---

## References

- `outputs/planning/sprints-29-38-plan-v2.md` — overall plan
- `outputs/planning/peer-reviews/{architect,data-scientist,quant-mentor}-review.md`
- `outputs/planning/multi-model-handoff-protocol.md`
- `outputs/planning/gemini-validation-playbook.md`
- `docs/analysis/6e-strategy-class-recommendation.md`
- `src/trading_research/core/{strategies,templates,instruments}.py`
- `src/trading_research/backtest/{engine,walkforward}.py`
- `src/trading_research/stats/stationarity.py`
