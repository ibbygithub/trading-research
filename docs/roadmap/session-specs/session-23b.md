# Session 23-b — Strategy & StrategyTemplate Protocols

**Agent fit:** claude
**Estimated effort:** M (2–4h)
**Depends on:** 23-a
**Unblocks:** 24, 25, 29, 30, 31, 32, 33

## Goal

Define the `Strategy` Protocol, the `StrategyTemplate` class, and the `TemplateRegistry`, so strategies become parameterized, knob-driven objects that can be instantiated from YAML presets without writing Python.

## Context

The ZN v1 and v2 strategies are currently written as Python classes with parameters hardcoded or passed via config. There is no formal interface declaring what a "strategy" is. There is no way for Ibby to say "instantiate the VWAP reversion template with band_sigma=2.5" without modifying a YAML and running a script that reads it.

Templates are the path to self-serve parameter exploration. A template is a strategy implementation plus a declared knob schema. Instantiating a template with a knob dict produces a concrete Strategy object.

## In scope

Create these files under `src/trading_research/core/`:

- `strategies.py`:
  - `Signal` dataclass — fields: `timestamp`, `direction` (Literal["long", "short", "flat"]), `strength: float`, `metadata: dict`.
  - `Position` dataclass — fields: `instrument_symbol`, `entry_time`, `entry_price: Decimal`, `size: int`, `direction`, `stop: Decimal`, `target: Decimal`.
  - `ExitDecision` dataclass — fields: `action` (Literal["hold", "exit", "scale_in", "scale_out"]), `reason: str`, `price: Decimal | None`.
  - `PortfolioContext` dataclass — fields: `open_positions: list[Position]`, `account_equity: Decimal`, `daily_pnl: Decimal`.
  - `Strategy` Protocol (runtime_checkable) with methods:
    - `generate_signals(bars: pd.DataFrame, features: pd.DataFrame, instrument: Instrument) -> list[Signal]`
    - `size_position(signal: Signal, context: PortfolioContext, instrument: Instrument) -> int`
    - `exit_rules(position: Position, current_bar: pd.Series, instrument: Instrument) -> ExitDecision`
  - Property: `name: str`, `template_name: str`, `knobs: dict`.

- `templates.py`:
  - `StrategyTemplate` class. Fields:
    - `name: str`
    - `human_description: str`
    - `strategy_class: type[Strategy]` — the class to instantiate.
    - `knobs_model: type[BaseModel]` — Pydantic model defining knob schema (name, type, default, range).
    - `supported_instruments: list[str] | Literal["*"]`
    - `supported_timeframes: list[str]`
  - `StrategyTemplate.instantiate(knobs: dict) -> Strategy` — validates knobs against schema, calls strategy_class with validated knobs.
  - `TemplateRegistry` class. Methods:
    - `register(template: StrategyTemplate)` — adds to registry.
    - `get(name: str) -> StrategyTemplate`
    - `list() -> list[StrategyTemplate]`
    - `instantiate(template_name: str, knobs: dict) -> Strategy` — convenience combining get + instantiate.
  - Module-level decorator `@register_template(name=..., ...)` that populates a module-global registry on import.

Create tests under `tests/core/`:

- `test_strategy_protocol.py`:
  - `test_dummy_strategy_satisfies_protocol` — define minimal strategy in test, verify `isinstance(s, Strategy)`.
  - `test_signal_dataclass` — Signal construction and field access.
  - `test_exit_decision_actions` — all four action literals round-trip.
- `test_template_registry.py`:
  - `test_register_and_get` — register a dummy template, retrieve by name.
  - `test_instantiate_with_valid_knobs` — instantiate, receive valid Strategy.
  - `test_instantiate_with_invalid_knobs_raises` — out-of-range value raises Pydantic ValidationError.
  - `test_instantiate_with_missing_knob_uses_default` — partial knob dict fills in defaults.
  - `test_list_templates` — returns all registered templates.
  - `test_duplicate_registration_raises` — registering same name twice raises.

## Out of scope

- Do NOT port existing ZN v1 or v2 strategies to templates. That's session 25 or later.
- Do NOT create any real templates (VWAP reversion, MACD pullback). Only the framework exists this session.
- Do NOT wire templates into the backtest CLI. That's F2 (CLI polish).
- Do NOT touch session 23-a code. Build on it.

## Acceptance tests

- [ ] `uv run pytest tests/core/test_strategy_protocol.py tests/core/test_template_registry.py -v` passes.
- [ ] `uv run pytest` — full suite passes.
- [ ] `python -c "from trading_research.core import Strategy, StrategyTemplate, TemplateRegistry; print('ok')"` succeeds.
- [ ] A minimal end-to-end script (in a test) registers a template, instantiates it with knobs, calls its `generate_signals` on a tiny synthetic bar DataFrame, and gets back a list of Signals.
- [ ] `ruff check src/trading_research/core/ tests/core/` — zero errors.
- [ ] `mypy src/trading_research/core/` — zero errors (if configured).

## Definition of done

- [ ] All acceptance tests pass.
- [ ] No modification to 23-a files (instruments.py, featuresets.py).
- [ ] Work log at `outputs/work-log/YYYY-MM-DD-session-23b.md`.
- [ ] Committed on feature branch `session-23b-strategy-template`.

## Persona review

- **Architect: required.** Protocol shape, knob schema design, registry mechanics.
- **Data scientist: required.** Reviews whether `Signal` and `ExitDecision` fields are sufficient for downstream statistical analysis (e.g., can we compute MFE/MAE from what Strategy produces).
- **Mentor: required.** Reviews whether the Strategy Protocol's three-method interface (generate_signals / size_position / exit_rules) is the right decomposition for how real strategies work. If mentor disagrees, spec gets revised before merge.

## Design notes

### Why Protocol, not ABC

Protocols allow structural typing. A strategy written inline in a Jupyter notebook or a test can satisfy the Protocol without importing or inheriting. This matches the research workflow. Use `@runtime_checkable` so `isinstance` works for runtime verification.

### Why three methods on Strategy

- `generate_signals` is pure: takes bars, features, and instrument; returns signals. No side effects. Easy to test.
- `size_position` is pure: takes a signal and portfolio context; returns integer contract count. Uses volatility targeting by default per CLAUDE.md.
- `exit_rules` is pure: takes an open position and the current bar; returns an ExitDecision. Supports the "Mulligan scale-in" via the `scale_in` action.

Keeping these three pure and separate means each can be tested in isolation and reused across templates.

### Knob schema example

For a hypothetical VWAP reversion template (NOT to be built this session, just for illustration of the schema):

```python
class VwapReversionKnobs(BaseModel):
    band_sigma: float = Field(2.0, ge=1.0, le=4.0, description="VWAP band width in std devs")
    stop_atr_multiplier: float = Field(2.0, ge=0.5, le=5.0)
    exit_method: Literal["vwap_return", "atr_trail", "time_stop"] = "vwap_return"
    time_stop_bars: int = Field(60, ge=5, le=500)
    regime_filter_adx_threshold: float | None = Field(None, ge=10.0, le=40.0)
```

This is what "knob descriptor" means — Pydantic enforces types and ranges. The human-readable description field is used by any future UI to render forms.

### `instantiate` pattern

```python
def instantiate(self, knobs: dict) -> Strategy:
    validated = self.knobs_model(**knobs)  # raises ValidationError on bad input
    return self.strategy_class(knobs=validated, template_name=self.name)
```

The strategy class takes `knobs` as a constructor argument and stores it. This allows the Strategy object to report its own configuration later (for trial registry provenance).

## Risks

- **Over-designing the knob schema.** Temptation: add UI-hint metadata, validation callbacks, computed defaults. Resist. Pydantic's built-in features (`Field(description=...)`, `ge/le`, `Literal`) are enough for session 23-b.
- **Strategy Protocol being wrong shape.** If during implementation the three-method split feels wrong (e.g., a strategy needs to see the full position history in `exit_rules`), stop and ask before changing the Protocol. Protocol changes later are expensive.
- **PortfolioContext being too narrow.** Daily pnl and open positions are probably sufficient for now. If a real strategy needs more (e.g., intraday drawdown), extend in a future session with a migration.

## Reference

- `docs/roadmap/session-specs/session-23a.md` — the Instrument and FeatureSet it depends on.
- `.claude/rules/platform-architect.md` — especially "Interfaces before implementations" and "Configuration over code".
- `.claude/rules/quant-mentor.md` — especially the section on Mulligan scale-in (legitimate re-entry on fresh signal).
- Existing strategy code in `src/trading_research/strategies/zn_macd_pullback.py` and VWAP v2 — reference for what the current "strategy" looks like, to verify the Protocol can accommodate it.

## Success signal

A test registers a minimal dummy template with two knobs, instantiates it with valid and invalid knob values, and the Strategy object round-trips through `isinstance(s, Strategy)`. That's the spine of the template system proven end-to-end.
