# Running the TradeStation downloader

This is a reference for the human (Ibby). The agent runs this for you; the
document exists so you can inspect what it does and run it yourself when you
want to.

## One-time setup

1. Copy `.env.example` to `.env` (already done — the file has placeholders).
2. Fill in the three credential fields in `.env`:
   - `TRADESTATION_CLIENT_ID`
   - `TRADESTATION_CLIENT_SECRET`
   - `TRADESTATION_REFRESH_TOKEN`
3. Run the auth verification script. It never prints your token:

   ```bash
   uv run python scripts/verify_tradestation_auth.py
   ```

   Expected output:

   ```
   OK  refresh succeeded
       access_token length : <some number>
       refresh latency     : 0.xxx s
       (the token itself is intentionally not printed)
   ```

   If this fails, stop. Fix credentials before proceeding.

## Running a historical download

One-month ZN smoke test:

```bash
uv run python -m trading_research.data.tradestation \
    --symbol ZN --start 2024-01-01 --end 2024-01-31
```

Outputs, relative to the project root:

- `data/raw/ZN_1m_2024-01-01_2024-01-31.parquet` — the canonical-schema parquet file.
- `data/raw/ZN_1m_2024-01-01_2024-01-31.metadata.json` — provenance.
  Contains: row count, expected-naive count, API calls made, rate limit hits,
  duration, continuous-contract method, request params, naive gap analysis,
  and the largest intra-series gaps found.

## What the downloader does NOT do (yet)

- It does not validate the file against the CME trading calendar. Naive gap
  counts only. Calendar validation is a session-03 deliverable under the
  `data-management` skill.
- It does not stitch individual contract months into a back-adjusted
  continuous series. It uses TradeStation's own `@ZN` continuous symbol,
  which is a defensible starting point but not the project's final answer.
  Multi-contract stitching with auditable roll dates is session-03 work.
- It supports only 1-minute bars. Higher timeframes come from resampling in
  `data-management`, not from re-downloading.

## Resuming a failed download

If a long pull dies mid-run, re-run the same command. The download function
hashes the input parameters to a stable `run_id` and writes each window to
`data/raw/.in_progress/<run_id>/`. Re-runs skip windows that already exist on
disk, so a 14-year pull that fails at year 12 does not restart from scratch.

The `.in_progress` directory is cleaned up only on successful completion.
If you need to force a clean re-download, remove the final parquet **and**
the corresponding `.in_progress` subdirectory.

## Sanity check: expected row count for a month of ZN

For one calendar month of CME Globex on ZN, expect roughly 30,000 bars
(23-hour Globex session × 22 trading days × 60 min ≈ 30,360). The naive gap
analysis in the metadata file will flag if the actual count is wildly off.
If it is, don't trust the data — surface it and we investigate before
building anything on top of it.
