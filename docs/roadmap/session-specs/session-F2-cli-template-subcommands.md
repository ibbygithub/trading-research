# Session F2 — CLI template subcommands (Gemini)

**Status:** Spec — slot anytime after sprint 29 (registry coupling done)
**Effort:** S (~1.5–2 hr)
**Agent fit:** Gemini 3.1 (Antigravity)
**Depends on:** Sprint 29 (TemplateRegistry on call path)
**Parallel-day candidate:** Day 5 alongside sprint 32

Follows `outputs/planning/multi-model-handoff-protocol.md`. Sonnet pre-writes
test fixtures; Gemini implements.

## Goal

Three new CLI subcommands so Ibby can interact with templates without writing
Python:

1. `trading-research list-templates` — prints all registered templates.
2. `trading-research describe-template <name>` — prints a template's knob
   schema with defaults, ranges, and human descriptions.
3. `trading-research backtest --template <name> --knobs k1=v1,k2=v2 ...` —
   runs a backtest using the registry, no YAML required for ad-hoc runs.

## In scope

### Pre-written test fixtures (Sonnet)

- `tests/cli/test_list_templates.py`:
  - Registers a synthetic template in a test-local registry.
  - Asserts `list-templates` output contains the name and description.
- `tests/cli/test_describe_template.py`:
  - Registers a template with known knob schema.
  - Asserts output contains every knob name, default, lower/upper bound,
    and description.
- `tests/cli/test_backtest_with_knobs.py`:
  - Registers a synthetic template; runs `backtest --template ... --knobs ...`
    against fixture bars; asserts trial record exists.

### Gemini implementation

- `src/trading_research/cli/templates.py` (new):
  - `list_templates_cmd()` Typer function.
  - `describe_template_cmd(name: str)` Typer function.
- `src/trading_research/cli/backtest.py` (extend):
  - `backtest --template ...` mode (alongside existing YAML mode).
  - Knobs parsed from comma-separated `k=v` pairs (use `pydantic` for type
    coercion via knobs_model).

### Output format for `describe-template`

```
Template: vwap-reversion-v1
  Description: Intraday VWAP mean reversion with extended hold window.
  Supported instruments: 6E
  Supported timeframes: 5m, 15m

Knobs:
  entry_threshold_atr   (float, default=2.2, range=[1.0, 4.0])
    Entry triggered when |vwap_spread / atr| exceeds this value.

  exit_target_atr       (float, default=0.3, range=[0.0, 1.5])
    Take profit when spread reverts to this band.

  ...
```

Pull descriptions from Pydantic Field's `description=` argument. (29b's
knob model should populate these — if missing, that's a 29b bug to flag,
not a Gemini extrapolation.)

## Validation

This sub-sprint is mostly CLI plumbing — no statistical method to canonical-
reference. Validation is via the pre-written tests (deterministic assertions
on output content).

## Acceptance

- [ ] All three pre-written test files pass.
- [ ] Running `uv run trading-research list-templates` after sprint 29 prints
      `vwap-reversion-v1`.
- [ ] Running `uv run trading-research describe-template vwap-reversion-v1`
      prints knobs with descriptions.
- [ ] No change to TemplateRegistry public API.

## Out of scope

- A web UI for templates.
- Mutating templates from CLI (registration is decorator-driven).
- Saving knob overrides to YAML automatically (manual save is fine).

## References

- `src/trading_research/core/templates.py`
- `src/trading_research/cli/main.py`
- `outputs/planning/gemini-validation-playbook.md`
