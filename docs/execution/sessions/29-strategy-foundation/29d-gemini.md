═══════════════════════════════════════════════════════════════
ROUTING HEADER — READ FIRST
═══════════════════════════════════════════════════════════════
Spec ID:           29d-gemini
Required model:    Gemini 3.1 (Antigravity)
Required harness:  Antigravity
Phase:             1 (hardening)
Effort:            M (~2 hr)
Entry blocked by:  29a (DONE), 29b (DONE)
Parallel-OK with:  29c (Sonnet, different files entirely)
Hand off to:       30a (after 29c also DONE)
Branch:            session-29-strategy-foundation (continue)
═══════════════════════════════════════════════════════════════

# 29d — OU bounds migration to instrument registry

This sub-sprint follows the **Gemini Validation Playbook** at
[`../../policies/gemini-validation-playbook.md`](../../policies/gemini-validation-playbook.md).
Read it before starting.

## Self-check

- [ ] I am Gemini 3.1 in Antigravity.
- [ ] 29a, 29b are DONE.
- [ ] `tests/contracts/test_ou_bounds_from_instrument.py` exists as a SKIP stub from 29a.
- [ ] `outputs/planning/gemini-validation-playbook.md` (or local path) is read.

If any unchecked: halt and emit MISROUTE.

## Validation contract for this sub-sprint

- Canonical reference: `statsmodels.api.OLS` for OU half-life via the
  regression `dx_t = α + β * x_{t-1} + ε`, half-life = -log(2) / β when β < 0.
- Parity test fixture: `tests/stats/test_ou_canonical_parity.py` (Sonnet
  pre-writes the fixture in 29a's stub stage; you fill the implementation
  side only — your `ou_half_life` function is what the test calls).
- Tolerance: `rtol=1e-9, atol=1e-12`.
- Escalation contact: this spec author. If tolerance fails by 2× or input
  shape differs from spec, escalate; do NOT loosen tolerance.

## What you implement

### 1. `src/trading_research/core/instruments.py`

Add field `tradeable_ou_bounds_bars: dict[str, tuple[float, float]]` to
the `Instrument` Pydantic model. Default factory matches current ZN values:

```python
tradeable_ou_bounds_bars: dict[str, tuple[float, float]] = Field(
    default_factory=lambda: {
        "1m": (5.0, 60.0),
        "5m": (3.0, 24.0),
        "15m": (2.0, 8.0),
    },
    description="Tradeable OU half-life bounds (lower, upper) in bars per timeframe."
)
```

### 2. `configs/instruments.yaml`

For 6E entry, add:
```yaml
tradeable_ou_bounds_bars:
  1m: [10, 240]
  5m: [10, 80]
  15m: [4, 30]
```

For ZN entry, ALSO add the explicit field with current ZN values:
```yaml
tradeable_ou_bounds_bars:
  1m: [5, 60]
  5m: [3, 24]
  15m: [2, 8]
```

This is intentional. ZN's existing classifications must NOT change. Pinning
the values explicitly in YAML protects against future default changes.

### 3. `src/trading_research/stats/stationarity.py`

- DELETE the module-level constant `_OU_TRADEABLE` (lines 43–47).
- The function that consumes the bounds (likely `compute_stationarity` or
  similar — find it via grep on `_OU_TRADEABLE`) must now take an `Instrument`
  argument and read from `instrument.tradeable_ou_bounds_bars`.
- Update all callers in the codebase. Search: `compute_stationarity` and
  `_OU_TRADEABLE`.

### 4. Implement contract test

`tests/contracts/test_ou_bounds_from_instrument.py` — replace skip body.
Two assertions:
- Passing 6E + 5m bounds yields TRADEABLE for OU half-life ~33 bars
  (which is what session 28 observed).
- Passing ZN + 5m yields the same classification observed pre-migration on
  the existing ZN report (the regression check).

### 5. Implement parity test

`tests/stats/test_ou_canonical_parity.py` — already a stub from 29a's
companion work. Per playbook Example C, with this exact body:

```python
import numpy as np
import statsmodels.api as sm
from trading_research.stats.stationarity import ou_half_life

SEED = 20260426
N = 5000

def test_ou_half_life_matches_ols_fit():
    rng = np.random.default_rng(SEED)
    true_beta = 0.85
    x = np.zeros(N)
    for i in range(1, N):
        x[i] = true_beta * x[i-1] + rng.normal()

    our_hl = ou_half_life(x)

    dx = np.diff(x)
    x_lag = x[:-1]
    X = sm.add_constant(x_lag)
    fit = sm.OLS(dx, X).fit()
    canonical_beta = fit.params[1]
    canonical_hl = -np.log(2) / canonical_beta if canonical_beta < 0 else np.inf

    np.testing.assert_allclose(
        our_hl.half_life_bars, canonical_hl,
        rtol=1e-9, atol=1e-12
    )
```

If `ou_half_life` doesn't return an object with `.half_life_bars`, escalate
— do NOT change the test or the function signature.

## Acceptance checks

- [ ] `tests/contracts/test_ou_bounds_from_instrument.py` passes.
- [ ] `tests/stats/test_ou_canonical_parity.py` passes.
- [ ] `uv run trading-research stationarity --symbol 6E` classifies as TRADEABLE.
- [ ] `uv run trading-research stationarity --symbol ZN` classifications IDENTICAL to pre-migration.
- [ ] `uv run pytest` full suite green.
- [ ] `_OU_TRADEABLE` constant no longer present in source.
- [ ] Handoff: `docs/execution/handoffs/29d-handoff.md` written.
- [ ] `current-state.md` updated: 29d → DONE.

## What you must NOT do

- Author your own validation tests against the canonical (the parity test
  above is the ONLY one; don't add others "for completeness").
- Loosen tolerance from `rtol=1e-9, atol=1e-12`.
- Change ZN bounds (would change ZN classifications — regression).
- Change the call signature of any public function beyond adding the
  `Instrument` parameter where required.
- Modify code in 29b's or 29c's scope (`vwap_reversion_v1.py`, `engine.py`).

## What you must escalate

- If the existing `ou_half_life` function has a different signature than
  `(series) -> ResultObject` — stop and report. Do NOT refactor.
- If the canonical statsmodels OLS produces different output shape than
  expected — stop and report.
- If 6E does not classify TRADEABLE under the new bounds — stop and report
  (this is a finding for the data scientist).
- If ZN classifications change at all — stop and report (regression).

## References

- Gemini validation playbook: [`../../policies/gemini-validation-playbook.md`](../../policies/gemini-validation-playbook.md)
- 29a handoff: [`../../handoffs/29a-handoff.md`](../../handoffs/29a-handoff.md)
- Architect on bounds location: [`outputs/planning/peer-reviews/architect-review.md`](../../../../outputs/planning/peer-reviews/architect-review.md) §3
- Original session 29 spec sub-sprint 29d: [`docs/roadmap/session-specs/session-29-strategy-foundation.md`](../../../roadmap/session-specs/session-29-strategy-foundation.md)
