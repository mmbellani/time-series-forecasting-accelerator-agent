# Skill · Intermittent / Croston Forecasting

**Folder:** `.github/skills/forecasting-intermittent/`
**Runs after:** [03/04 profiling + clustering](Pipeline-Overview) and [06 Train / Tune](06-Train-Test-Select-Tune)

## What it does

Forecasts **intermittent / lumpy demand** (many zero periods, spiky series — spare parts, sparse revenue lines) with **Croston-family** statistical models, and benchmarks them against the LightGBM baseline.

Runs **twice**: globally and **by `profile_cluster`**, scored on the same backtest windows as the notebook-06 `y_hat_*` forecasts.

## Models

- **CrostonClassic**, **CrostonOptimized**, **CrostonSBA** (Syntetos–Boylan Approximation)
- **TSB** (Teunter–Syntetos–Babai)
- **ADIDA**, **IMAPA** (temporal aggregation approaches)

These pair naturally with the `intermittent` / `lumpy` profiles from [03 Profiling](03-Profiling-Intermittent).

## Metrics

**MAE**, **RMSE**, **WMAPE**, **ME** (bias) — WMAPE is zero-safe, important for sparse series.

## Notes

- **Dependency:** `statsforecast>=1.7.0` (not yet in `requirements.txt`).
- Best applied to the series that clustering/profiling flags as non-regular.

## Files

- `forecasting_intermittent.py` · `templates/example_usage.py` · report template
