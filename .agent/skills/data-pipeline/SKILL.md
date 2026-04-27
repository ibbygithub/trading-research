---
name: data-pipeline
description: Manages the end-to-end data lifecycle from RAW acquisition to CLEAN validation and FEATURE engineering.
---

# Goal
Ensure a "Single Source of Truth" for all market data, adhering to the three-layer architectural model: RAW (immutable) -> CLEAN (validated) -> FEATURES (indicators).

# Instructions
1. **Layer Progression**:
    - **RAW**: Downloaded data must be stored untouched in `data/raw/` with a corresponding `.metadata.json`.
    - **CLEAN**: Every RAW dataset must pass the `data-quality-check` skill before being promoted to CLEAN parquet.
    - **FEATURES**: Only datasets in the CLEAN layer can have indicators or time-series features added.
2. **Resampling Law**:
    - 1-minute bars are the canonical base. All higher timeframes (3m, 5m, 15m, etc.) must be resampled from 1m CLEAN data, never re-downloaded.
3. **The Trio Review**:
    - **Architect**: Verify the `Instrument` Protocol is used for all metadata (tick size, multiplier) and that no logic is hardcoded.
    - **Scientist**: Audit the resampling logic for look-ahead bias and ensure the CLEAN layer remains indicator-free.
    - **Mentor**: Confirm the instrument physics (session hours, roll methodology) match the CME standards in `configs/instruments.yaml`.

# Constraints
- **Immutable CLEAN**: CLEAN parquet files MUST NOT contain indicators. If indicators are needed, they belong in a FEATURES parquet.
- **Configuration over Code**: All instrument specs must be pulled from `configs/instruments.yaml`. Hardcoding any value in the pipeline is a critical failure.
- **Loud Failure**: The pipeline must crash and report the specific failure (e.g., "Missing Session") rather than producing empty or interpolated data.

# Examples
- **User**: "Prepare the ZN data for the MACD strategy."
- **Agent**: (Downloads RAW) -> (Runs quality-check) -> (Promotes to CLEAN) -> (Resamples to 5m FEATURES with MACD) -> "ZN data is ready in the FEATURES layer. Architect verified the schema.".