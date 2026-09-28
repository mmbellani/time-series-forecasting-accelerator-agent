# Skill · Moving Average Forecasting

**Folder:** `.github/skills/forecasting-moving-average/`
**Runs after:** [03/04 profiling + clustering](Pipeline-Overview) and [06 Train / Tune](06-Train-Test-Select-Tune)

## What it does

Forecasts with classic **moving-average** models — the simple rolling-window mean (`WindowAverage`) and its seasonal variant (`SeasonalWindowAverage`) — and benchmarks them against the LightGBM baseline.

Every model is run **twice**:
1. **Globally** — scored across the whole panel.
2. **By `profile_cluster`** — the best window size can differ per segment.

Both are scored on the **same backtest windows** as the notebook-06 `y_hat_*` forecasts, for an apples-to-apples comparison.

## The models

| Model | Idea | Best for |
|-------|------|----------|
| `WindowAverage` | mean of the last N observations | smooth, level series |
| `SeasonalWindowAverage` | mean of the last N same-season observations | stable seasonal patterns |

## Metrics

Scale-free / robust: **MAE**, **RMSE**, **WMAPE**, **ME** (bias). Convention `error = y - yhat` (positive ME = under-forecast).

## Public API

`build_models` · `forecast_global` · `forecast_by_cluster` · `predict_future` · `evaluate_forecasts` · `select_best` · `compare_to_baseline` · `narrate_comparison`

## Notes

- **Dependency:** `statsforecast>=1.7.0` (not yet in `requirements.txt`).
- Moving averages are **inherently local**; "global vs cluster" changes scoring/selection, not pooling. They lag trends — watch the `ME` bias.

## Files

- `forecasting_moving_average.py` · `templates/example_usage.py` · `templates/forecasting_moving_average_report.md`
