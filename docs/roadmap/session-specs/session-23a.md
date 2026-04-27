# Session 23-a — Instrument & FeatureSet Protocols

**Agent fit:** claude
**Estimated effort:** M (2–4h)
**Depends on:** —
**Unblocks:** 23-b, 24, 25, 26, 28, B1, D1

## Goal

Define the `Instrument` and `FeatureSet` interfaces with their registries, populated and tested, so every subsequent session can program against an Instrument object rather than a symbol string, and against a versioned FeatureSet hash rather than a name.

## Context

Three hardcodings of `"ZN"` in the data layer (OI-010/011/012) are the visible symptom. The invisible cost is that every new instrument requires touching multiple files. This session solves the first half of the problem — Instrument and FeatureSet. Session 23-b adds Strategy and StrategyTemplate. Splitting the work keeps each session under a hard 4-hour cap.

## In scope

Create these files under `src/trading_research/core/`:

- `__init__.py` — re-export public classes.
- `instruments.py`:
  - `Instrument` Pydantic model with fields listed in the Design Notes below.
  - `InstrumentRegistry` class with `get(symbol) -> Instrument`, `list() -> list[Instrument]`, and lazy-loaded cache.
- `featuresets.py`:
  - `FeatureSpec` dataclass (feature `name`, `params` dict).
  - `FeatureSet` Pydantic model with fields: `name`, `version`, `features: list[FeatureSpec]`, `code_version` (filled at build time).
  - `FeatureSet.compute_hash()` — stable hash from canonicalized spec (see Design Notes).
  - `FeatureSetRegistry` with `get(name: str, version: str) -> FeatureSet`, `list() -> list[FeatureSet]`.

Create/update config files:

- `configs/instruments.yaml` — entries for ZN, 6E, 6A, 6C. Every field in the `Instrument` model populated. Use TradeStation symbol mappings from memory (ZN → `@TY`, 6E → `@EU`, 6A → `@AD`, 6C → `@CD`). **Include commission and margin fields per the Design Notes.**
- `configs/featuresets/base-v1.yaml` — codify the existing base-v1 feature set as a versioned YAML. This may require reading current feature-building code to extract the implicit list.

Create these tests under `tests/core/`:

- `test_instrument_registry.py`:
  - `test_load_yaml` — registry loads without error.
  - `test_get_zn` — `registry.get("ZN")` returns populated Instrument.
  - `test_get_6e` — `registry.get("6E")` returns populated Instrument with all fields.
  - `test_unknown_raises` — `registry.get("NONEXISTENT")` raises `KeyError`.
  - `test_tick_value_consistency` — for ZN, `tick_value_usd == tick_size * contract_multiplier` (catches data-entry bugs).
  - `test_commission_fields_present` — every instrument has `commission_per_side_usd` set.
  - `test_margin_fields_present` — every instrument has `intraday_initial_margin_usd` set.
- `test_featureset_hash.py`:
  - `test_stable_hash` — two FeatureSets with same spec produce same hash.
  - `test_reorder_feature_list_same_hash` — feature list order does not affect hash (canonicalization).
  - `test_different_param_different_hash` — changing one feature param changes the hash.
  - `test_code_version_affects_hash` — different `code_version` produces different hash.

## Out of scope

- Do NOT create `strategies.py` or `templates.py`. That's session 23-b.
- Do NOT refactor any existing data-layer code. That's session 25.
- Do NOT remove the hardcoded `"ZN"` strings yet. They stay until session 25.
- Do NOT modify the trial registry format. That's session 24.
- Do NOT wire the `FeatureSetRegistry` into the feature-building code. That's session 25.
- Do NOT create strategy templates or port v1/v2 strategies to templates. That's session 23-b or later.

## Acceptance tests

- [ ] `uv run pytest tests/core/test_instrument_registry.py tests/core/test_featureset_hash.py -v` — all tests pass.
- [ ] `uv run pytest` — full suite still passes, no regressions in the 401 existing tests.
- [ ] `uv run python -c "from trading_research.core import InstrumentRegistry; i = InstrumentRegistry().get('6E'); print(i.model_dump_json(indent=2))"` — prints a populated 6E Instrument JSON.
- [ ] `uv run python -c "from trading_research.core import FeatureSetRegistry; fs = FeatureSetRegistry().get('base', 'v1'); print(fs.compute_hash())"` — prints a hex hash.
- [ ] `ruff check src/trading_research/core/ tests/core/` — zero errors.
- [ ] `mypy src/trading_research/core/` — zero errors (if mypy is configured in project).

## Definition of done

- [ ] All acceptance tests pass.
- [ ] No new files outside scope.
- [ ] Work log at `outputs/work-log/YYYY-MM-DD-session-23a.md`.
- [ ] Committed on feature branch `session-23a-instrument-featureset`.
- [ ] PR opened against `develop` (not merged — that's human).

## Persona review

- **Architect: required.** Reviews Protocol shape, field naming, registry loading semantics. Required before merge.
- **Data scientist: required.** Reviews FeatureSet hashing — specifically that hash canonicalization is correct and that code_version is included. Required before merge.
- **Mentor: optional.** No market logic here, but may review commission/margin values for accuracy.

## Design notes

### `Instrument` model fields

```python
class Instrument(BaseModel):
    symbol: str                          # canonical short: "ZN", "6E", "6A", "6C"
    tradestation_symbol: str             # e.g. "@TY" for ZN continuous
    name: str                            # human-readable: "10-Year Treasury Note"
    exchange: str                        # "CBOT", "CME", "NYMEX", etc.
    asset_class: Literal["rates", "fx", "equity_index", "commodity", "crypto"]

    # Contract specs
    tick_size: Decimal                   # e.g. Decimal("0.015625") for ZN
    tick_value_usd: Decimal              # dollars per tick, e.g. 15.625 for ZN
    contract_multiplier: Decimal         # tick_value / tick_size
    is_micro: bool                       # True for MES, MNQ, M6E, etc.

    # Commissions (confirmed values from Ibby 2026-04-19)
    commission_per_side_usd: Decimal     # 1.75 for regular, 0.50 for micros

    # Margins (full contract intraday initial — confirmed values from Ibby 2026-04-19)
    intraday_initial_margin_usd: Decimal # 500 for ZN and standard currency futures
    overnight_initial_margin_usd: Decimal | None  # nullable; not always known

    # Sessions (all times America/New_York)
    session_open_et: time                # full session open
    session_close_et: time               # full session close
    rth_open_et: time                    # regular trading hours open
    rth_close_et: time                   # regular trading hours close
    timezone: str = "America/New_York"

    # Calendar + rollover
    calendar_name: str                   # pandas_market_calendars name, e.g. "CMEGlobex_Bond"
    roll_method: Literal["panama", "ratio", "none"]
```

### Values to populate in `configs/instruments.yaml`

```yaml
instruments:
  ZN:
    symbol: ZN
    tradestation_symbol: "@TY"
    name: "10-Year Treasury Note"
    exchange: "CBOT"
    asset_class: "rates"
    tick_size: "0.015625"    # 1/64 of a point (ZN trades in 1/64ths actually 1/2 of 1/32)
    tick_value_usd: "15.625"
    contract_multiplier: "1000"
    is_micro: false
    commission_per_side_usd: "1.75"
    intraday_initial_margin_usd: "500"
    overnight_initial_margin_usd: null
    session_open_et: "18:00"
    session_close_et: "17:00"
    rth_open_et: "08:20"
    rth_close_et: "15:00"
    calendar_name: "CMEGlobex_Bond"
    roll_method: "panama"

  6E:
    symbol: 6E
    tradestation_symbol: "@EU"
    name: "Euro FX"
    exchange: "CME"
    asset_class: "fx"
    tick_size: "0.00005"
    tick_value_usd: "6.25"
    contract_multiplier: "125000"
    is_micro: false
    commission_per_side_usd: "1.75"
    intraday_initial_margin_usd: "500"
    overnight_initial_margin_usd: null
    session_open_et: "18:00"
    session_close_et: "17:00"
    rth_open_et: "08:20"       # FX has no "RTH" in the equity sense; use liquid window
    rth_close_et: "15:00"
    calendar_name: "CMEGlobex_FX"
    roll_method: "panama"

  6A:
    symbol: 6A
    tradestation_symbol: "@AD"
    name: "Australian Dollar"
    exchange: "CME"
    asset_class: "fx"
    tick_size: "0.00005"
    tick_value_usd: "5.00"
    contract_multiplier: "100000"
    is_micro: false
    commission_per_side_usd: "1.75"
    intraday_initial_margin_usd: "500"
    overnight_initial_margin_usd: null
    session_open_et: "18:00"
    session_close_et: "17:00"
    rth_open_et: "08:20"
    rth_close_et: "15:00"
    calendar_name: "CMEGlobex_FX"
    roll_method: "panama"

  6C:
    symbol: 6C
    tradestation_symbol: "@CD"
    name: "Canadian Dollar"
    exchange: "CME"
    asset_class: "fx"
    tick_size: "0.00005"
    tick_value_usd: "5.00"
    contract_multiplier: "100000"
    is_micro: false
    commission_per_side_usd: "1.75"
    intraday_initial_margin_usd: "500"
    overnight_initial_margin_usd: null
    session_open_et: "18:00"
    session_close_et: "17:00"
    rth_open_et: "08:20"
    rth_close_et: "15:00"
    calendar_name: "CMEGlobex_FX"
    roll_method: "panama"
```

**Tick sizes and contract values should be verified against CME specs during implementation.** The values above are approximations; the agent should look up CME contract specs and adjust if needed. If any value cannot be verified, flag in the work log and ask before defaulting.

### `FeatureSet` hash canonicalization

Hash must be stable under:
- Reordering `features` list (sort by `name` before hashing).
- Dict key ordering in YAML (use `json.dumps(..., sort_keys=True)`).
- Whitespace differences.

Hash must change under:
- Any feature parameter change.
- Feature addition or removal.
- `code_version` change (current git short SHA at build time).

Implementation sketch: serialize `(name, version, sorted_features, code_version)` to canonical JSON, hash with blake2b, take first 16 hex chars.

### Decimal precision

Use `Decimal` for tick_size, tick_value, contract_multiplier, commissions, and margins. Float arithmetic will produce wrong P&L numbers eventually. This is non-negotiable.

## Risks

- **Verifying real CME tick sizes / contract values.** Some values above may be off — e.g. ZN's tick size is technically `1/64 of 1 point` = `0.015625`; 6E is `0.00005` for a point value of $6.25. Agent should confirm against CME contract specs page and flag any discrepancy.
- **Unknown overnight margin.** If TradeStation has a specific overnight margin for ZN, populate it. Otherwise leave null and document.
- **base-v1 featureset extraction.** The current feature-building code may not cleanly enumerate the feature list. If extraction is ambiguous, stop and ask — do not guess.

## Reference

- `docs/roadmap/sessions-23-50.md` — where this session fits.
- `docs/handoff/status-report-session-22.md` — current platform state, open issues OI-010/011/012.
- `CLAUDE.md` — project conventions.
- `.claude/rules/platform-architect.md` — architectural standards.
- Existing feature-building code under `src/trading_research/features/` (or wherever it lives) — to extract the current base-v1 feature list.
- Memory entry `ts_symbol_mapping.md` — confirmed ZN → @TY mapping.
- CME contract specs — tick sizes and contract values authoritative source.

## Success signal

`python -c "from trading_research.core import InstrumentRegistry; [print(i.symbol, i.commission_per_side_usd, i.intraday_initial_margin_usd) for i in InstrumentRegistry().list()]"` prints four instruments with their commission and margin values. That one line being green proves Instrument is real.
