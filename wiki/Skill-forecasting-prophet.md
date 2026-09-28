# Skill · Prophet Forecasting

**Folder:** `.github/skills/forecasting-prophet/`
**Runs after:** [03/04 profiling + clustering](Pipeline-Overview) and [06 Train / Tune](06-Train-Test-Select-Tune)

## What it does

Forecasts with **Meta/Facebook Prophet** — a decomposable additive model of **trend + seasonality + holidays** — and benchmarks it against the LightGBM baseline.

Runs **twice**: globally over the entire panel and **by `profile_cluster`**, scored on the same backtest windows as the notebook-06 `y_hat_*` forecasts.

## When Prophet shines

- Strong, interpretable **seasonality** (yearly / weekly / daily)
- **Holiday** and event effects
- Trend **changepoints**
- Robustness to missing data

Tunable: `changepoint_prior_scale`, `seasonality_mode` (additive/multiplicative), custom seasonalities and holidays.

## Metrics

**MAE**, **RMSE**, **WMAPE**, **ME** (bias), on identical `[unique_id, ds]` windows via inner join.

## Notes

- **Dependency:** `prophet` (not yet in `requirements.txt`).
- Additive/decomposable model vs gradient boosting — the report highlights which wins per cluster.

## Files

- `forecasting_prophet.py` · `templates/example_usage.py` · `templates/forecasting_prophet_report.md`
