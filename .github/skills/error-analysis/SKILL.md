---
name: error-analysis
description: "Evaluate time-series forecast accuracy and decompose the error by calendar variables. USE FOR: evaluate forecast, forecast accuracy, error analysis, MAE, MAPE, ME (mean error / bias), RMSE, WMAPE, sMAPE, where is the forecast wrong, error by month/quarter/week/day-of-week, error distribution, error box-plot, seasonality of error, forecast bias, over-forecasting vs under-forecasting, worst error buckets, compare model accuracy. Built for the LightGBM + mlforecast pipeline (notebook 06 Train/Tune) that produces per-cluster models and <scenario>_forecasts tables with y (actual) and y_hat_* (predicted) columns. RUN BEFORE the forecast-explainability skill so the worst error buckets and points define the explainability scope. DO NOT USE FOR: computing feature importance or explaining a single prediction (use forecast-explainability), training or tuning models (use notebook 06), feature engineering (use notebook 05), clustering (use notebook 04)."
license: MIT
metadata:
  author: Time Series Forecasting Accelerator
  version: "1.0.0"
  runs_before: forecast-explainability
---

# Error-Analysis Skill

This skill **evaluates forecast accuracy** and **decomposes the error by calendar
variables**. It turns actuals-vs-predictions into the four headline metrics —
**MAE, MAPE, ME, RMSE** — and, for each of them, a **box-plot of the error
distribution** across `year`, `quarter`, `month`, `week`, and `dayofweek`, so you can
see *where* and *when* the forecast breaks down.

It is designed for the Time Series Forecasting Accelerator pipeline, where
**notebook 06** writes `<scenario>_forecasts` with columns `unique_id`, `ds` (date),
`y` (actual), and one or more `y_hat_*` prediction columns (e.g. `y_hat_identity`,
`y_hat_std`), plus a selected best model.

## Run this BEFORE `forecast-explainability`

Error analysis first answers *"where is the forecast wrong?"* and identifies the model,
series, dates, and calendar buckets that need investigation. Then
`forecast-explainability` answers **why** the model produced those values using feature
weights (gain / split) and per-point SHAP contributions.

Recommended flow:

```mermaid
flowchart LR
    A[error-analysis<br/>where/when is the output wrong?] --> B[worst_buckets → pick points]
    B --> C[forecast-explainability<br/>why did the model output this?]
    C --> D[explain_prediction on those points<br/>investigate the miss]
    D --> E[hierarchical-reconciliation<br/>roll up approved findings]
```

1. First run this skill to quantify accuracy and localize error by calendar bucket.
2. Pass the worst buckets (`worst_buckets()`) to `forecast-explainability`.
3. Run `explain_prediction()` on the selected points to see
   *which feature weights* produced the miss.
4. Run `hierarchical-reconciliation` after explainability when an approved hierarchy is
   available.

## When To Use

| You want to… | This skill provides |
|--------------|---------------------|
| Score overall accuracy | `metric_summary()` → MAE, MAPE, ME, RMSE (+ WMAPE, sMAPE) |
| Compare model variants | `compare_models()` over all `y_hat_*` columns |
| Break a metric down by season | `metrics_by_calendar(errors, by="month")` |
| See the error *distribution*, not just the mean | `error_boxplot()` / `boxplot_grid()` |
| See absolute-error spread at the data's frequency | Required MAE box plot grouped by weekday for daily data, week for weekly data, etc. |
| Find where the model is worst | `worst_buckets()` |
| Produce a stakeholder report | Templates in `templates/` |
| Translate errors into business language | `narrate_errors()` |

## Core Concepts

### Error convention

The module uses the forecasting-standard residual (Hyndman convention):

```
error = y_true - y_pred        # actual minus forecast
```

- `error > 0` → **under-forecast** (actual exceeded the forecast)
- `error < 0` → **over-forecast** (forecast exceeded the actual)
- `ME` (Mean Error / bias) near 0 means the forecast is **unbiased**.

### The four metrics

| Metric | Formula | Reads as | Sensitive to |
|--------|---------|----------|--------------|
| **MAE** | `mean(|error|)` | typical miss size, in target units | — (robust) |
| **MAPE** | `mean(|error| / |y_true|) * 100` | typical miss size, in % | small/zero actuals |
| **ME** | `mean(error)` | direction & size of **bias** | cancellation of +/− |
| **RMSE** | `sqrt(mean(error²))` | miss size, penalizing large errors | outliers / spikes |

MAPE is undefined where `y_true == 0`; those rows are dropped from MAPE only (MAE / ME /
RMSE still use them). `WMAPE` and `sMAPE` are reported as robust alternatives for
intermittent / near-zero series.

### Calendar decomposition & box-plots

Every metric is decomposed across calendar variables (`year`, `quarter`, `month`,
`week`, `dayofweek`). For each variable, `error_boxplot()` shows the **distribution** of
the per-observation error component behind the metric:

| Metric | Per-row column plotted | The box tells you |
|--------|------------------------|-------------------|
| MAE | `abs_error` | magnitude of misses per bucket |
| MAPE | `ape` (%) | relative miss size per bucket |
| ME | `error` (signed) | bias direction & spread (0-line = unbiased) |
| RMSE | `squared_error` | variance of misses (right-skewed — compare, don't read spread) |

A box-plot (not just a bar of the mean) exposes **spread, skew, and outliers** — e.g. a
month with a modest mean MAE but a long upper whisker is driven by a few bad weeks, which
is a different problem than a uniformly poor month.

### Required MAE box plot matched to data frequency

Always include a **MAE error-distribution box plot whose calendar grouping matches the
frequency of the evaluated data**, in addition to any broader calendar breakdowns.
Use the pipeline's configured frequency for the evaluated series; if it is unavailable,
infer it from sorted, distinct timestamps **within each series**, not from pooled
timestamps across series. If the frequency is irregular or ambiguous, ask the user to
confirm it rather than silently defaulting to monthly grouping. For mixed-frequency
data, produce a separate plot for each frequency group.

| Data frequency | X-axis buckets | `by` |
|----------------|----------------|------|
| Subdaily / hourly | Hour of day (0-23) | `hour` |
| Daily / business-daily | Day of week (Mon-Sun; observed days only) | `dayofweek` |
| Weekly | ISO week of year (1-53; observed weeks only) | `week` |
| Monthly | Month of year (Jan-Dec) | `month` |
| Quarterly | Quarter of year (Q1-Q4) | `quarter` |
| Annual | Observed years | `year` |

For subdaily data, add `errors["hour"] = errors["ds"].dt.hour` before plotting;
`compute_errors()` already supplies the other calendar columns. For custom frequencies,
confirm the appropriate grouping with the user.

Call `error_boxplot(errors, by=frequency_bucket, metric="MAE")`. Each box must contain
the **per-observation absolute errors** in that bucket, not a single pre-aggregated MAE.
Their mean is the bucket's MAE; the box displays the median, quartiles, whiskers, and
outliers of the absolute-error distribution. Label the y-axis as absolute error in
target units, state the data frequency and grouping in the title, and report bucket
sample counts and MAE using `metrics_by_calendar()`. Flag sparse or single-observation
buckets, whose distributions cannot be interpreted reliably. Save and include this plot
in the report; the all-calendar grid does not replace it.

## Workflow

1. **Assemble actuals vs predictions.** Join `<scenario>_forecasts` to actuals on
   `[unique_id, ds]` so each row has `y` and the chosen `y_hat_*` column.
2. **Compute per-row errors.** `compute_errors(df, y_true="y", y_pred="y_hat_best")`
   returns a tidy frame with `error`, `abs_error`, `squared_error`, `ape` and the
   calendar columns.
3. **Score overall & compare models.** `metric_summary()` for the headline numbers;
   `compare_models()` to rank `y_hat_*` variants.
4. **Identify frequency & decompose.** Select `frequency_bucket` using the table above.
   Run `metrics_by_calendar(errors, by=frequency_bucket)` and add broader calendar
   breakdowns as needed.
5. **Plot distributions.** Always produce
   `error_boxplot(errors, by=frequency_bucket, metric="MAE")`. Add plots for other metrics
   and optionally `boxplot_grid(errors, metric="MAE")` for an at-a-glance page.
6. **Localize & hand off.** `worst_buckets()` picks the worst buckets; feed points from
   them into `explain_prediction()` (the `forecast-explainability` skill).
7. **Narrate.** `narrate_errors()` for prose, then drop it into a report from `templates/`.

## Usage

```python
from evaluate import (
    compute_errors,
    metric_summary,
    compare_models,
    metrics_by_calendar,
    error_boxplot,
    boxplot_grid,
    worst_buckets,
    narrate_errors,
)

# 0) Pick the prediction column (e.g. the best model from notebook 06)
y_pred = best_model_name          # e.g. "y_hat_identity"

# 1) Per-row errors + calendar decomposition columns
errors = compute_errors(forecasts_df, y_true="y", y_pred=y_pred, date_col="ds")

# 2) Headline metrics
print(metric_summary(errors, y_true="y", y_pred=y_pred))

# 3) Compare all model variants
print(compare_models(forecasts_df, y_true="y", sort_by="MAE"))

# 4) Match the grouping to the confirmed frequency (weekly example)
frequency_bucket = "week"        # Daily: "dayofweek"; monthly: "month"
print(metrics_by_calendar(errors, by=frequency_bucket, y_pred=y_pred))
for metric in ["MAE", "MAPE", "ME", "RMSE"]:
    error_boxplot(
        errors, by=frequency_bucket, metric=metric,
        title=f"Weekly data: {metric} error distribution by ISO week of year",
    )

# 5) One-page grid (MAE across all calendar variables)
boxplot_grid(errors, metric="MAE")

# 6) Worst buckets → hand off to forecast-explainability
print(worst_buckets(errors, by=frequency_bucket, metric="MAE", top_n=3))

# 7) Narrative
print(narrate_errors(errors, y_true="y", y_pred=y_pred, unit="USD"))
```

## Boundaries

- ✅ Read actuals/forecast tables; compute metrics; decompose by calendar; plot
  distributions; generate narratives. Read-only with respect to data and models.
- ✅ Handle any tidy actuals-vs-predictions frame, and multiple `y_hat_*` columns.
- ⚠️ `matplotlib` is required only for `error_boxplot` / `boxplot_grid`; the metric
  functions have no plotting dependency.
- ⚠️ MAPE / sMAPE are unstable for near-zero actuals (intermittent series) — prefer
  MAE / WMAPE there and say so in the report.
- 🚫 Do not retrain, re-tune, or overwrite models or tables.
- 🚫 Do not assert *causes* of error from this skill alone — confirm the "why" via
  `forecast-explainability` (feature weights / SHAP) before claiming a root cause.

## Files

| File | Purpose |
|------|---------|
| `evaluate.py` | Core functions: per-row errors, MAE/MAPE/ME/RMSE, calendar decomposition, box-plots, worst-bucket ranking, narrative generation. |
| `templates/error_analysis_report.md` | Stakeholder-ready accuracy + error-decomposition report. |
| `templates/example_usage.py` | End-to-end runnable example against the pipeline outputs. |
