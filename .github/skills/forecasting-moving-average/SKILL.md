---
name: forecasting-moving-average

description: "Forecast time series with classic MOVING-AVERAGE models (rolling-window mean and seasonal window average) and benchmark them against the LightGBM baseline. USE FOR: moving average forecasting, moving average model, rolling mean forecast, simple moving average (SMA), window average, WindowAverage, SeasonalWindowAverage, seasonal moving average, rolling-window baseline, naive smoothing baseline, average of last N periods, average of last N same-season periods, run a moving-average model globally and per profile-cluster, compare moving average vs LightGBM, moving average vs gradient boosting, which model wins per cluster, baseline benchmark, statsforecast window-average models. Runs each model twice — as a GLOBAL model over the entire panel and BY profile_cluster — then compares accuracy (MAE/RMSE/WMAPE/ME) to the notebook 06 LightGBM y_hat_* baseline. Built for the pipeline where notebooks 03/04 label series by profile_cluster and notebook 06 writes <scenario>_forecasts. RUN AFTER profiling/clustering (notebooks 03/04) so profile_cluster exists, and AFTER notebook 06 so the LightGBM baseline exists. DO NOT USE FOR: feature importance / explaining a single prediction (use forecast-explainability), decomposing error by calendar (use error-analysis), rolling forecasts up a hierarchy (use hierarchical-reconciliation), intermittent/Croston demand (use forecasting-intermittent), training LightGBM (use notebook 06), clustering (use notebook 04)."
license: MIT
metadata:
  author: Time Series Forecasting Accelerator
  version: "1.0.0"
  runs_after: [profiling, clustering, notebook-06-train-tune]
---

# Moving-Average Forecasting Skill

This skill **forecasts time series with classic moving-average models** — the
simple rolling-window mean (`WindowAverage`) and its seasonal variant
(`SeasonalWindowAverage`) — and **benchmarks them against the pipeline's LightGBM
baseline**.

Per the request that shaped it, every model is run **twice**:

1. **Globally** — fitted across the *entire* panel in one `StatsForecast` run.
2. **By `profile_cluster`** — fitted separately per cluster so the best
   moving-average configuration can be picked for each segment.

Both runs are scored on the **same backtest windows** as the LightGBM `y_hat_*`
forecasts from **notebook 06**, so the comparison is apples-to-apples.

It is designed for the Time Series Forecasting Accelerator pipeline, where the
panel has `unique_id` (series id), `ds` (date), `y` (actual value), a
`profile_cluster` grouping column (from notebooks 03/04), and where notebook 06
writes `<scenario>_forecasts` with `y` and one or more `y_hat_*` columns.

## Run this AFTER profiling/clustering and notebook 06

- **Notebooks 03/04** create the `profile_cluster` label used for the per-cluster
  run.
- **Notebook 06** produces the LightGBM `y_hat_*` baseline this skill compares
  against.

```mermaid
flowchart LR
    A[NB03/04 profiling + clustering<br/>profile_cluster label] --> C
    B[NB06 Train/Tune<br/>LightGBM y_hat_* baseline] --> C
    C[moving-average forecasting<br/>window-average global + per cluster] --> D[compare_to_baseline]
    D --> E[winner per scope: MovingAverage vs LightGBM]
```

## When To Use

| You want to… | This skill provides |
|--------------|---------------------|
| Build the moving-average model set | `build_models()` |
| Forecast with a moving average over the whole panel | `forecast_global()` |
| Forecast with a moving average per `profile_cluster` | `forecast_by_cluster()` |
| Produce genuine future-horizon forecasts | `predict_future()` |
| Score models with scale-free metrics | `evaluate_forecasts()` (MAE/RMSE/WMAPE/ME) |
| Pick the winner overall or per cluster | `select_best()` |
| Benchmark vs the LightGBM baseline | `compare_to_baseline()` |
| Summarize the result in prose | `narrate_comparison()` |

## Core Concepts

### The models

| Model | Idea | Best for |
|-------|------|----------|
| **WindowAverage** | Forecast = mean of the last `window_size` observations (SMA) | Smooth, level series with little trend |
| **SeasonalWindowAverage** | Forecast = mean of the last `window_size` *same-season* observations (e.g. average of the last N Januaries) | Series with a stable seasonal pattern |

Several window sizes are evaluated by default (`WindowAverage_3`,
`WindowAverage_6`, `WindowAverage_12`, plus seasonal variants) so the best span
can be selected per scope. Optional `Naive` / `SeasonalNaive` baselines can be
added via `build_models(add_naive_baselines=True)` for context.

### Why these metrics

The headline metrics are scale-free or robust, so they work across mixed-magnitude
series and stay defined when actuals are zero:

| Metric | Formula | Reads as |
|--------|---------|----------|
| **MAE** | `mean(|y - yhat|)` | typical miss size, in target units |
| **RMSE** | `sqrt(mean((y - yhat)²))` | miss size, penalizing large misses |
| **WMAPE** | `sum(|y - yhat|) / sum(|y|) * 100` | error as % of total volume (zero-safe) |
| **ME** | `mean(y - yhat)` | bias: `> 0` under-forecast, `< 0` over-forecast |

Error convention (Hyndman): `error = y - yhat` (actual minus forecast).

### Global vs. by-cluster — what actually differs

Moving-average models are **inherently local** (one fit per series). "Global" and
"by cluster" therefore differ in **scoring and model selection**, not in whether
series are pooled:

- **Global**: all series scored together → one winning moving-average
  configuration for the whole dataset.
- **By `profile_cluster`**: each cluster scored on its own → the winning
  window size can differ per cluster (short windows track fast-moving segments;
  longer/seasonal windows suit stable ones).

### Fair comparison to LightGBM

`compare_to_baseline()` inner-joins the moving-average backtest to the
`<scenario>_forecasts` baseline on `[unique_id, ds]`, so **both families are
scored on the exact same observations**. It labels each model `MovingAverage` or
`LightGBM (baseline)` and returns the winner overall and (optionally) per cluster.

## Workflow

1. **Confirm inputs.** A panel with `unique_id`, `ds`, `y`, and `profile_cluster`
   (from notebooks 03/04), plus the `<scenario>_forecasts` baseline (notebook 06).
   Confirm the `freq` (e.g. `"MS"` monthly), horizon `h`, and `season_length`
   with the user.
2. **Build models.** `models = build_models()` (window averages + seasonal) — or a
   subset via `window_sizes` / `seasonal_window_sizes`.
3. **Global run.** `cv_global = forecast_global(df, h=h, freq="MS", models=models)`.
4. **Per-cluster run.** `cv_cluster = forecast_by_cluster(df, h=h, freq="MS",
   group_col="profile_cluster", models=models)`.
5. **Score & select.** `evaluate_forecasts(...)` then `select_best(...)` overall
   and with `group_by="profile_cluster"`.
6. **Benchmark vs LightGBM.** `compare_to_baseline(cv_global, forecasts_df)` and
   `compare_to_baseline(cv_cluster, forecasts_df, group_by="profile_cluster")`.
7. **Narrate & report.** `narrate_comparison(...)`, then a report from `templates/`.

## Usage

```python
from forecasting_moving_average import (
    build_models,
    forecast_global,
    forecast_by_cluster,
    evaluate_forecasts,
    select_best,
    compare_to_baseline,
    narrate_comparison,
)

H, FREQ, SEASON = 3, "MS", 12           # horizon + granularity + season (confirm with user)
models = build_models(season_length=SEASON)   # WindowAverage_{3,6,12} + SeasonalWindowAverage

# 1) GLOBAL — entire panel
cv_global = forecast_global(df, h=H, freq=FREQ, models=models, n_windows=3)

# 2) BY profile_cluster
cv_cluster = forecast_by_cluster(
    df, h=H, freq=FREQ, group_col="profile_cluster", models=models, n_windows=3,
)

# 3) Score the moving-average models
print(evaluate_forecasts(cv_global))                                   # overall
print(evaluate_forecasts(cv_cluster, group_by="profile_cluster"))      # per cluster

# 4) Compare to the LightGBM baseline (<scenario>_forecasts has y_hat_* cols)
res_global = compare_to_baseline(cv_global, forecasts_df)
print(res_global["metrics"])            # MovingAverage vs LightGBM, ranked by MAE
print(res_global["winner"])

res_cluster = compare_to_baseline(cv_cluster, forecasts_df, group_by="profile_cluster")
print(narrate_comparison(res_cluster["metrics"], res_cluster["winner"],
                         unit="units", group_by="profile_cluster"))
```

## Dependencies

- **`statsforecast`** is required for the forecasting functions (`WindowAverage`,
  `SeasonalWindowAverage`) and is **not yet** in `requirements.txt` (the pipeline
  ships `mlforecast` / `utilsforecast` only). Add it before running:

  ```
  statsforecast>=1.7.0
  ```

  Flag this as a new dependency at the phase checkpoint before installing.
- The **evaluation / narration** helpers (`evaluate_forecasts`, `select_best`,
  `compare_to_baseline`, `narrate_comparison`) use only `numpy` / `pandas` and
  work on any tidy actuals-vs-predictions frame.

## Boundaries

- ✅ Fit moving-average models globally and per `profile_cluster`; backtest via
  rolling cross-validation; score with scale-free metrics; benchmark vs the
  LightGBM baseline; narrate the result.
- ✅ Handle any subset of window sizes and optional naive baselines.
- ⚠️ `statsforecast` is a new dependency — confirm/install it first.
- ⚠️ Moving-average models are inherently local; "global vs cluster" changes
  scoring and selection, not pooling. Say so in the report.
- ⚠️ Moving averages lag trends and cannot extrapolate; expect bias on
  fast-trending series — read the `ME` column and note it.
- ⚠️ Compare on identical `[unique_id, ds]` windows — `compare_to_baseline()`
  inner-joins to enforce this; if the join is empty the backtest windows differ.
- 🚫 Do not retrain, re-tune, or overwrite the LightGBM models or the
  `<scenario>_forecasts` table — this skill is additive and read-only w.r.t. the
  baseline.

## Files

| File | Purpose |
|------|---------|
| `forecasting_moving_average.py` | Core functions: model catalogue, global & per-cluster backtests, future forecasts, metrics, best-model selection, baseline comparison, narrative. |
| `templates/forecasting_moving_average_report.md` | Stakeholder-ready benchmark report (global + per-cluster + vs LightGBM). |
| `templates/example_usage.py` | End-to-end runnable example against the pipeline outputs. |
