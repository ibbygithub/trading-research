# Data Pipeline Technical Protocol

This document provides the technical execution patterns for the `data-pipeline` skill, migrated from the legacy `pipeline.md` and `data-layering.md`.

## Environment & Tooling
- **Manager**: `uv`.
- **Engine**: `pandas` and `pyarrow` for Parquet processing.
- **Calendar**: `pandas-market-calendars` for CME session awareness.

## Execution Patterns

### 1. Promoting RAW to CLEAN
The agent must invoke the promotion script through `uv` to ensure calendar-aware validation is enforced.

```python
from trading_research.data.layering import promote_to_clean
from pathlib import Path

# Architect: Use Pathlib for Windows/Linux compatibility
raw_path = Path("data/raw/ZN_1m.parquet")
clean_path = promote_to_clean(raw_path)

# Scientist: Verify integrity status after promotion
print(f"CLEAN Parquet generated: {clean_path}")
```

### 2. Standard Resampling Pattern
All HTF (Higher Time Frame) views must follow this resample-only rule:

```python
def resample_bars(df, frequency):
    # Mentor: Ensure OHLCV aggregation is correct (Open=first, High=max, Low=min, Close=last, Vol=sum)
    logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
    return df.resample(frequency).apply(logic).dropna()
```

## Naming Conventions
To maintain provenance, files must follow this structure:

- **RAW**: `{SYMBOL}_1m_{START}_{END}.parquet`
- **CLEAN**: `{SYMBOL}_1m_clean.parquet`
- **FEATURES**: `{SYMBOL}_{FREQ}_features_{VERSION}.parquet`

## Registry Reference
Always load instrument specs from `configs/instruments.yaml`:

- `tick_size`: Minimum price movement.
- `contract_multiplier`: `$ value per tick`.
- `calendar_name`: CME or other market identifier.

## Next Steps
1. Save the first block as `/.agent/skills/data-pipeline/SKILL.md`.
2. Save the second block as `/.agent/skills/data-pipeline/references/pipeline-logic.md`.
3. To finish this skill, you should also move your `docs/Tradestation-trading-symbol-list.md` into `/.agent/skills/data-pipeline/references/` for agent-only reference.
