# Forecast Error-Analysis Report — {{SCENARIO}}

**Model:** {{MODEL_NAME}} (LightGBM via mlforecast, notebook 06)
**Generated:** {{DATE}}
**Evaluation window:** {{EVAL_START}} → {{EVAL_END}}
**Target:** {{TARGET}} ({{UNIT}})
**Series evaluated:** {{N_SERIES}} • **Points evaluated:** {{N_POINTS}}

> Run **after** the `forecast-explainability` report. This report says *where/when* the
> forecast is wrong; the explainability report says *why the model produced that value*.

---

## 1. Executive summary

> One-paragraph, plain-language answer to *"how accurate is the forecast, and where does
> it break down?"* Auto-fill from `narrate_errors(errors, unit="{{UNIT}}")`.

{{NARRATIVE_SUMMARY}}

---

## 2. Overall accuracy

Error convention: `error = actual − forecast`. Positive ME ⇒ **under-forecasting**;
negative ME ⇒ **over-forecasting**.

| Metric | Value | Reads as |
|--------|------:|----------|
| MAE  | {{MAE}} {{UNIT}} | typical miss size |
| MAPE | {{MAPE}} % | typical miss size (relative) |
| ME (bias) | {{ME}} {{UNIT}} | direction & size of bias |
| RMSE | {{RMSE}} {{UNIT}} | miss size, penalizing large errors |
| WMAPE | {{WMAPE}} % | weighted MAPE (robust to small actuals) |
| sMAPE | {{SMAPE}} % | symmetric MAPE |

*Source:* `metric_summary(errors)`.

**Model comparison** (if several `y_hat_*` variants exist):

| Model | MAE | MAPE % | ME | RMSE |
|-------|----:|-------:|---:|-----:|
| {{model_1}} | {{mae_1}} | {{mape_1}} | {{me_1}} | {{rmse_1}} |
| {{model_2}} | {{mae_2}} | {{mape_2}} | {{me_2}} | {{rmse_2}} |
| … | … | … | … | … |

*Source:* `compare_models(forecasts_df, sort_by="MAE")`.

---

## 3. Error decomposed by calendar variable

Each metric is broken down across calendar variables and shown as a **box-plot of the
error distribution** — this exposes spread, skew, and outliers, not just the average.

### 3.1 MAE — magnitude of misses

![MAE by month](img/{{SCENARIO}}_mae_by_month.png)
![MAE grid](img/{{SCENARIO}}_mae_grid.png)

*Source:* `error_boxplot(errors, by="month", metric="MAE")` /
`boxplot_grid(errors, metric="MAE")`.

| {{BY}} | n | MAE | MAPE % | ME | RMSE |
|--------|--:|----:|-------:|---:|-----:|
| {{bucket_1}} | {{n_1}} | {{mae_1}} | {{mape_1}} | {{me_1}} | {{rmse_1}} |
| {{bucket_2}} | {{n_2}} | {{mae_2}} | {{mape_2}} | {{me_2}} | {{rmse_2}} |
| … | … | … | … | … | … |

*Source:* `metrics_by_calendar(errors, by="{{BY}}")`.

### 3.2 MAPE — relative miss size

![MAPE by month](img/{{SCENARIO}}_mape_by_month.png)

> Flag buckets with near-zero actuals where MAPE is inflated; prefer MAE/WMAPE there.

### 3.3 ME — bias (over- vs under-forecast)

![ME by month](img/{{SCENARIO}}_me_by_month.png)

> Boxes above the 0-line = systematic under-forecast; below = over-forecast.

### 3.4 RMSE — variance / large-error sensitivity

![RMSE by month](img/{{SCENARIO}}_rmse_by_month.png)

> Squared-error distribution is right-skewed; use it to *compare* buckets, not to read
> symmetric spread.

---

## 4. Error hot-spots (worst buckets)

The buckets to investigate first, ranked by MAE.

| Calendar var | Worst bucket | n | MAE | MAPE % | ME |
|--------------|--------------|--:|----:|-------:|---:|
| month | {{worst_month}} | {{n}} | {{mae}} | {{mape}} | {{me}} |
| quarter | {{worst_quarter}} | {{n}} | {{mae}} | {{mape}} | {{me}} |
| week | {{worst_week}} | {{n}} | {{mae}} | {{mape}} | {{me}} |
| dayofweek | {{worst_dow}} | {{n}} | {{mae}} | {{mape}} | {{me}} |

*Source:* `worst_buckets(errors, by="month", metric="MAE")`.

---

## 5. Root-cause hand-off to `forecast-explainability`

For each hot-spot above, select representative points inside the bucket and run
`explain_prediction(model, X_row, feature_cols)` to see which feature weights produced
the miss.

- [ ] Worst month `{{worst_month}}` → explain {{K}} representative points.
- [ ] Worst quarter `{{worst_quarter}}` → explain {{K}} representative points.
- [ ] Check whether hot-spots align with the dominant feature family from the
      explainability report (e.g. `calendar` features under-serving a seasonal peak).

---

## 6. Interpretation notes & caveats

- **Bias vs. accuracy:** small MAE with large |ME| means consistent directional bias —
  fixable with a level/seasonal correction; large MAE with ME≈0 means noisy misses.
- **MAPE instability:** unreliable near zero actuals (intermittent series) — read
  MAE / WMAPE instead in those buckets.
- **Distribution over mean:** a long upper whisker means a few bad points drive the
  bucket — investigate those specific points, not the whole bucket.
- **Correlation ≠ cause:** this report localizes error; confirm the *why* via
  `forecast-explainability` before asserting a root cause.

---

## 7. Recommended actions

- [ ] Address the top error hot-spot(s) identified in §4.
- [ ] If ME shows systematic bias, add/adjust bias-correction in notebook 06.
- [ ] If seasonal buckets dominate, revisit calendar/seasonal features in notebook 05.
- [ ] Re-evaluate after changes and compare metric tables here.
