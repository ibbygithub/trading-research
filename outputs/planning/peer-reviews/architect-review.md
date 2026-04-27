# Peer Review — Sprints 29–38 Plan
## Reviewer: Platform Architect persona
Date: 2026-04-26
Reviewing: `outputs/planning/sprints-29-38-plan.md` v1, `sprints-29-38-risks.md` v1, code under `src/trading_research/{core,backtest,eval,strategies,stats}/`, configs/

I read the plan against the actual code. The plan is shaped well; the code it talks to is partially built but has couplings that the plan does not yet acknowledge. If we run the plan as written, we will paper over those couplings and pay for it in sprints 35–38 when the paper-trading loop fights them. This review names each one.

---

## 1. Walkforward bypasses the registry that just got built

`src/trading_research/backtest/walkforward.py:33` reads:

```python
signal_module_path = cfg_raw["signal_module"]
...
mod = importlib.import_module(signal_module_path)
signals_df = mod.generate_signals(bars, **signal_params)
```

Walkforward takes a Python module path string and dynamically imports it, then calls `generate_signals` as a free function. It does not use `TemplateRegistry`. The Strategy Protocol that session 23 built (`core/strategies.py`) is **not on the call path**.

This means:
- Sprint 29 cannot just "wire `vwap_reversion_v1` into the backtest engine." The engine has no opinion about templates. We have two parallel strategy systems: the Protocol+Registry one (used by no production code yet) and the module-import one (used by walkforward and by both ZN strategies in `strategies/`).
- The plan's implicit assumption that `register_template` produces a thing the backtest engine will consume is false today.

**Required architectural decision before sprint 29 begins:**

There are three options and I want one chosen explicitly, not arrived at by drift:

**Option A — Walkforward consumes templates.** Add a `template: vwap-reversion-v1` field to the strategy YAML; walkforward instantiates from registry; engine calls `strategy.generate_signals(...)`. The two ZN strategies get retrofitted as templates (low risk — tests already exist). One strategy system, the registry one.

**Option B — Templates are CLI-facing only; walkforward stays free-function.** Templates exist for `describe-template` and the human-facing CLI (sprint F2); walkforward keeps its dynamic-import path. Two strategy systems, but explicit boundary.

**Option C — Adapter.** A `TemplateBackedSignalModule` wrapper that exposes a `generate_signals` free function over a registered template. Bridges the systems. Compatible with both halves.

My recommendation: **A, but staged**. Sprint 29 wires the new 6E strategy through the registry; sprint 30 confirms it runs in walkforward; sprints F1/F2 retrofit the ZN strategies and decommission the dynamic-import path. This collapses to one system within the 10-sprint window without forcing a big-bang refactor.

The plan must commit to one option in 29a. Sonnet cannot make this call mid-implementation in 29b.

---

## 2. `BacktestConfig.quantity` is a hardcoded position size — `Strategy.size_position` is unreachable

`backtest/engine.py` carries `quantity: int` in `BacktestConfig`. This is the position size used for every trade. Meanwhile the Strategy Protocol has:

```python
def size_position(self, signal, context, instrument) -> int: ...
```

The engine never calls it. So the entire vol-targeting / risk-adjusted sizing surface that CLAUDE.md mandates is bypassed today.

The plan does not list this as an item. It must.

**Add to the plan:** sprint 29 (or a new sprint 29.5) wires `Strategy.size_position(signal, context, instrument)` into the engine's order-construction path. Without this:
- Sprint 30 v1 backtest is fixed-quantity, not vol-targeted. The Calmar/Sharpe numbers are not the numbers a real strategy would produce.
- Sprint D1 loss limits, when wired, will halt on absolute USD numbers that do not reflect the actual sizing model.
- Sprint 32 Mulligan scale-in cannot be implemented honestly — scale-in size is by definition computed from current portfolio context, which means `size_position` must be on the call path.

This blocks Track C. Promote to in-scope for sprint 29.

---

## 3. The OU half-life bounds belong in the instrument registry, not in `stats/stationarity.py`

`stats/stationarity.py:43-47` carries instrument-agnostic bounds. The data scientist correctly flagged that this needs per-instrument calibration. From the architect's side: it is also a single-source-of-truth violation. We have `configs/instruments.yaml` with all the per-instrument facts. Tradeable OU bounds are an instrument fact (driven by the instrument's daily range and trading session structure). They belong there.

**Required:**
- New field on Instrument: `tradeable_ou_bounds: dict[timeframe, tuple[float, float]]` (or similar).
- `stats/stationarity.py` reads from the Instrument, not from a module constant.
- Default fallback (when an instrument does not have explicit bounds) lives in one place, defensibly named.
- `core/instruments.py` Pydantic model gets the field with a sensible default.

This is a clean refactor and it kills the recalibration risk for every future instrument. It also makes 6A/6C/6N (Track H) free — the bounds get defined once when the instrument enters the registry, never as a parallel surgery to the suite.

The data scientist asked for "per-instrument bounds." The right answer is "in the instrument."

---

## 4. The `gemini-validation-playbook` is the most important supporting doc to write

The plan's multi-model strategy stands or falls on whether Gemini-shipped code is verifiable. Right now the verification is "Gemini's session rules say validate against canonical references." That is a policy, not a mechanism.

The mechanism we need:
- **Spec writes the test.** The fixture, the golden values, the tolerance, the seed. All written by the spec author (Opus or Sonnet) before Gemini sees the spec.
- **Gemini fills in implementation only.** Gemini does not author its own validation tests. If Gemini's test passes against canonical and Gemini's test was written by Gemini, we have validated nothing.
- **One golden artifact per public method.** A small JSON/parquet fixture committed to the repo that asserts: input X produces output Y. If Gemini "fixes" the implementation in a way that changes Y, the test fails loudly.

This is non-negotiable for Gemini sessions. Write `outputs/planning/gemini-validation-playbook.md` with the pattern, and reference it from every Gemini sprint spec.

I will write a draft below as part of this review pass.

---

## 5. Trial registry version-skew is more dangerous than the plan acknowledges

Plan v1 risk register says "trial registry version-skew breaks v1-vs-v2 comparison." The actual code at `eval/trials.py` already enforces cohort separation by `code_version` and refuses cross-cohort DSR. Good.

What the plan does not address: **between sprints 29 and 33, the engine itself may change.** Sprint 29.5 (which I'm adding above) wires `size_position`. That is an engine change. Every trial after that change is in a new cohort. Sprint 30's v1 backtest was the *first* trial in that cohort. Sprint 33's v2 backtest will be in the same cohort only if no further engine change happens between 30 and 33.

**Required:**
- Sprint 30a, 31b, 32b, 33a all log the engine fingerprint (git SHA + hash of `engine.py`) when recording a trial.
- 33b gate procedure includes: "verify cohort_label is consistent across v1, v1+regime, v1+regime+mulligan, v2. If any cohort transition occurred, justify in writing or rerun the affected trials."

This is a one-line addition to the trial recording call but it must be in the plan.

---

## 6. Paper-trading bridge is two systems pretending to be one

Plan sprint 35 says "wire signal generator → order submitter → fill listener → trade log writer → daily report." Reading this as architect: which signal generator? The walkforward one? The Strategy Protocol one? They are not the same path.

If sprint 29 picks Option A (registry-only), this is moot because everything goes through `Strategy.generate_signals(...)`. If sprint 29 picks Option B or C, sprint 35 has to bridge the dynamic-import strategy world and the live-trading world, and we will have two different signal pipelines firing the same strategy in two different processes.

This is one more reason to commit to Option A in sprint 29.

---

## 7. Featureset version is in the manifest but not on the live data path

Session 28 added `featureset_hash` to the FEATURES manifest. Good. Sprint 35 paper trading needs to verify, every time it loads a feature row at runtime, that the featureset hash matches the strategy's expected featureset. Otherwise we ship a strategy trained on `base-v1` features into a system that quietly upgraded to `base-v2`.

The plan does not name this. It needs to.

**Add to sprint 35 acceptance:** at startup and on every feature parquet swap, the live loop verifies `featureset_hash == strategy.expected_featureset_hash`. Mismatch is a hard halt, not a warning.

---

## 8. Two strategies named "vwap-reversion" — namespace collision risk

There is already `src/trading_research/strategies/zn_vwap_reversion.py`. Sprint 29 adds `vwap_reversion_v1`. Without explicit namespacing, the registry name will collide with the existing ZN strategy if/when it gets retrofitted.

**Required naming convention to be added to the plan:**
- Templates: `<strategy-class>-<version>`. Examples: `vwap-reversion-v1`, `vwap-reversion-v2`.
- Strategy *instances* (per CLAUDE.md): `<template>-<instrument>-<config-hash-short>`. Example: `vwap-reversion-v1-6E-a3f5b1`.
- Existing ZN strategies on retrofit become `zn-vwap-reversion-v0` (legacy marker) until decommissioned.

This is a five-minute architectural decision that prevents a six-month-from-now bug. Bake it into 29a.

---

## 9. `gui/` and `replay/` exist but the plan does not reference them

There is already a `src/trading_research/gui/` and a `replay/` directory. The plan's sprint 38 ("trader's-desk polish") talks about HTML status pages without acknowledging what already exists.

**Required:**
- Sprint 38a (Opus design) must read `gui/` and `replay/` first and decide: extend, reuse, or replace. "What does Ibby open in the morning" depends on the answer.
- If the answer is "reuse," 38b is small. If the answer is "extend," 38b needs an interface contract on what data the cockpit reads. If the answer is "replace," that is a separate sprint and 38 becomes scoping-only.

The plan implicitly assumes "build new." That is the most expensive answer and probably the wrong one.

---

## 10. Test coverage for cross-module contracts is missing

Today's tests are mostly per-module unit tests. The plan adds coupling work (registry ↔ engine, engine ↔ live loop, instrument registry ↔ stationarity suite). Each new coupling needs a contract test, not a unit test.

**Required new test files:**
- `tests/contracts/test_registry_to_engine.py` — every registered template can be instantiated and its `generate_signals` called by the engine without error on a synthetic dataset.
- `tests/contracts/test_strategy_protocol_invariants.py` — every concrete Strategy satisfies the Protocol AND the Mulligan freshness invariant from the data scientist's review.
- `tests/contracts/test_featureset_hash_propagation.py` — strategy expects featureset X; manifest reports hash X; live loop accepts. Strategy expects X; manifest reports Y; live loop refuses.
- `tests/contracts/test_instrument_to_stationarity.py` — per-instrument OU bounds are read from instrument registry, not from module constants.

The plan should land these in the sprints that introduce the corresponding coupling, not in a separate "testing sprint" at the end.

---

## 11. What the plan got right architecturally

- Splitting Opus design from Sonnet implementation at the spec boundary is the right pattern. The cost saving is real and the quality is, in my limited observation, equal or better than monolithic Opus sessions.
- Putting Track D in parallel with Track C is correct. Loss limits are independent of strategy, and starting them late means sprint 35 stalls.
- Sprint 37 as an explicit hardening sprint, not a "buffer," is mature. Most plans skip this and pay the cost in sprints 38–40 anyway.
- The escape valves at sprint 33 are honest. A plan without escape valves is a plan that cannot fail, which means it cannot succeed either.

---

## 12. Required updates I want to see in v2 of the plan

1. Sprint 29a explicit decision on Walkforward / Registry coupling (Option A, B, C). My vote: A staged.
2. Sprint 29.5 added — wire `Strategy.size_position` into the engine. Or fold into 29b with effort upgrade.
3. OU bounds move into instrument registry, not just suite recalibration. 29c becomes a proper migration.
4. Strategy naming convention written into 29a.
5. Engine fingerprint recorded on every trial; 33b checks cohort consistency explicitly.
6. Featureset hash check on the live data path in sprint 35.
7. Sprint 38a starts with audit of `gui/` and `replay/` — extend / reuse / replace decision before any new HTML.
8. Contract test files added to sprints that introduce couplings.
9. `gemini-validation-playbook.md` written and referenced from every Gemini sprint spec.
10. The Mulligan freshness rule promoted to a Protocol-level invariant in `core/strategies.py`, with contract tests.

---

## What I will not sign off on

I will not sign off architecturally if:
- Sprint 29 ships without a written decision on Walkforward / Registry coupling.
- `Strategy.size_position` remains unreachable through sprint 33.
- OU bounds remain in `stats/stationarity.py` as module constants when 6A/6C arrive in Track H.
- Sprint 38 builds a new HTML cockpit without first reading what `gui/` and `replay/` already do.
- Gemini sprints rely on Gemini-authored validation tests against canonical references.

If those five hold, the plan is structurally sound and worth executing.

---

## Architect's recommendation on session 29 split

Given the new in-scope items above, here is how 29 should actually split:

| Sub | Model | Workload | Effort |
|---|---|---|---|
| 29a | Opus 4.7 | Architectural decisions: registry-vs-walkforward (A/B/C), naming convention, OU bounds location, Mulligan-freshness invariant; spec for 29b–29d | M |
| 29b | Sonnet 4.6 | Implement registry coupling, retrofit walkforward to consume templates (or adapter, depending on 29a decision); 6E `vwap-reversion-v1` template implementation | M |
| 29c | Sonnet 4.6 | Wire `Strategy.size_position` into engine; migrate `quantity` to fallback only; add contract test for sizing path | M |
| 29d | Gemini 3.1 | OU bounds migration: move to instrument registry; per-fixture parity test against existing 6E classification under new bounds; canonical-method parity tests for OU half-life vs. statsmodels OLS | M |

Yes, that is four sub-sprints in one calendar day's worth of human direction. It is also four pieces of work that genuinely cannot be combined without losing the model-fit benefit. The effort numbers (M+M+M+M) suggest two days, not one — promote sprint 29 to a two-day window in the daily-throughput table.

This is the cost of being honest about the current state of the code. The original sprint 29 plan was sized for a codebase that was further along than the actual one.
