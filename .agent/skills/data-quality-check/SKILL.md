---
name: data-quality-check
description: Use when you need to validate bar datasets against the exchange trading calendar to ensure no silent gaps or holiday confusion.
---

# Goal
Verify the integrity of OHLCV data in `data/raw/` using the canonical `validate_bar_dataset` engine to prevent downstream backtest corruption.

# Instructions
1. **Target Identification**: Locate the target `.parquet` file in `data/raw/`. If no specific symbol is provided by the user, identify the most recently downloaded or largest file for analysis.
2. **Context Assembly**: Extract the symbol, start date, and end date from the filename or the associated `.metadata.json`.
3. **Execution Protocol**: 
    - Execute the validation using `uv run python` as defined in the `references/quality-protocol.md`.
    - Consult the **Data Scientist** persona to interpret gaps strictly—overnight gaps must be distinguished from unexpected data feed drops.
4. **The Trio Review**:
    - **Scientist**: Flag any gaps that violate the "No Silent Gaps" law in the Project Constitution.
    - **Architect**: Ensure the generated `.quality.json` report is saved at the same path as the raw data for provenance.
    - **Mentor**: Provide a "vibe check" on whether the gap size would typically lead to a strategy halt.
5. **Output**: Present a summary of the "Top 3 Gaps" and the "Interpreted Summary" in plain English. Wait for Ibby's "GO" before promoting this data to the CLEAN layer.

# Constraints
- Do not run validation without confirming the canonical `calendar_name` (e.g., CME) in `configs/instruments.yaml`.
- Do not attempt to refactor the internal `validate_bar_dataset` logic; treat it as an immutable platform utility.
- Naive timestamps are prohibited; ensure all validation output uses UTC or ET as per the constitution.

# Examples
- **User**: "Check the quality of the new ZN download." 
- **Agent**: (Runs skill) -> "Scientist confirms 3 gaps found. Architect has saved the report. Mentor notes gaps are standard overnight thin-liquidity periods. Proceed to CLEAN?".