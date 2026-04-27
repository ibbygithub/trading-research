# Data Quality Implementation Protocol

This document provides the exact technical implementation for the `data-quality-check` skill.

## Python Execution Logic
The agent must use the following pattern to invoke the validator through the `uv` environment:

```python
from pathlib import Path
from datetime import date
from trading_research.data.validate import validate_bar_dataset

# Configuration variables to be populated by the agent based on file discovery
SYMBOL = "{{SYMBOL}}"
START_DATE = date({{YYYY}}, {{MM}}, {{DD}})
END_DATE = date({{YYYY}}, {{MM}}, {{DD}})
FILE_PATH = Path('data/raw/{{FILENAME}}.parquet')

report = validate_bar_dataset(
    FILE_PATH,
    SYMBOL,
    START_DATE,
    END_DATE,
)

# Mandatory summary extraction
print(f"Total Gaps Found: {report.gap_count}")
print(f"Integrity Status: {report.status}")
Interpretation Standards
When the agent reviews the report object, it must adhere to these standards:

Gap Definition: Any missing 1-minute bar that should exist based on the pandas-market-calendars schedule for that instrument.

Holiday Awareness: Distinguish between "Market Closed" (no gap) and "Market Open but no data" (Critical Gap).

Report Storage: The output JSON must follow the naming convention {FILENAME}.quality.json in the same directory as the source parquet.

Instrument Metadata
Consult configs/instruments.yaml to retrieve these fields before execution:

tick_size

calendar_name

session_hours


---

**Architect's Note:** If you have successfully saved that block, your **Data Quality C