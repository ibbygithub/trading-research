# Session 29 — Strategy Foundation & Coupling Fixes

## Routing matrix

| Sub-sprint | File | Required model | Effort |
|---|---|---|---|
| 29a | [`29a-opus.md`](29a-opus.md) | **Opus 4.7** | M |
| 29b | [`29b-sonnet.md`](29b-sonnet.md) | **Sonnet 4.6** | M |
| 29c | [`29c-sonnet.md`](29c-sonnet.md) | **Sonnet 4.6** | M |
| 29d | [`29d-gemini.md`](29d-gemini.md) | **Gemini 3.1 (Antigravity)** | M |

**Dispatcher:** route the matching file to the matching model. Do NOT route
this README to a model. Do NOT route a different sub-sprint's file to the
wrong model.

## Goal of session 29

End state across both calendar days:

1. `vwap-reversion-v1` is a registered template; `walkforward.py` instantiates
   strategies via `TemplateRegistry`.
2. `BacktestEngine` calls `Strategy.size_position(...)`; `BacktestConfig.quantity`
   is fallback only.
3. Tradeable OU half-life bounds live in `configs/instruments.yaml`,
   per-instrument; `stats/stationarity.py` reads from `Instrument`.
4. Naming convention for templates and strategy instances documented.
5. Mulligan freshness invariant documented at the Strategy Protocol level.
6. ZN existing classifications unchanged (regression).
7. 6E classifies as TRADEABLE under per-instrument bounds.

## Sequencing

```
Day 1:    29a (Opus, morning)  →  29b (Sonnet, afternoon)
                                      ‖
                                   D1 (Sonnet, parallel)
Day 2:    29c (Sonnet, morning)  ‖  29d (Gemini, day 2)
```

## Cross-cutting acceptance (session 29 done)

```bash
uv run pytest tests/                                # Full suite green
uv run pytest tests/contracts/                      # All contract tests pass
uv run trading-research describe-template vwap-reversion-v1   # Lists knobs
uv run trading-research stationarity --symbol 6E    # 6E TRADEABLE
uv run trading-research stationarity --symbol ZN    # ZN classifications IDENTICAL
```

## Branch
`session-29-strategy-foundation`

## References
- [`../../plan/master-execution-plan.md`](../../plan/master-execution-plan.md)
- [`../../policies/multi-model-handoff-protocol.md`](../../policies/multi-model-handoff-protocol.md)
- [`../../policies/gemini-validation-playbook.md`](../../policies/gemini-validation-playbook.md)
- Original spec (kept for context): [`docs/roadmap/session-specs/session-29-strategy-foundation.md`](../../../roadmap/session-specs/session-29-strategy-foundation.md)
