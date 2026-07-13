# Intermittent-Demand Forecast Benchmark — {{SCENARIO}}

_Generated: {{DATE}} · Horizon (h): {{H}} · Frequency: {{FREQ}} · Backtest windows: {{N_WINDOWS}}_

## 1. Summary

- **Series scope:** {{N_SERIES}} series, of which {{N_INTERMITTENT}} are profiled as
  intermittent / lumpy / erratic / spikes (from notebooks 03/04).
- **Models evaluated:** {{MODEL_LIST}} (Croston family + relatives) vs the LightGBM
  baseline ({{BASELINE_COLS}}) from notebook 06.
- **Headline result:** {{ONE_LINE_VERDICT}}

> Metrics are intermittent-safe: **MAE**, **RMSE**, **WMAPE**, **ME** (bias).
> MAPE is intentionally omitted — undefined on zero-demand periods.

## 2. Global run (entire panel)

All series scored together; one winning intermittent model for the whole dataset.

| Model | Family | MAE | RMSE | WMAPE (%) | ME (bias) | n |
|-------|--------|-----|------|-----------|-----------|---|
| {{...rows from res_global["metrics"]...}} | | | | | | |

- **Best overall:** {{GLOBAL_WINNER}} ({{GLOBAL_WINNER_FAMILY}}).
- **Intermittent vs LightGBM:** {{GLOBAL_DELTA_NARRATIVE}}

## 3. By `profile_cluster`

Each cluster scored on its own; the winning intermittent model may differ per
segment (lumpy clusters often prefer SBA/TSB; smoother ones prefer Croston).

| profile_cluster | Best model | Family | MAE | RMSE | WMAPE (%) | ME |
|-----------------|-----------|--------|-----|------|-----------|----|
| {{...rows from select_best(..., group_by="profile_cluster")...}} | | | | | | |

- **Segments where intermittent models win:** {{WON}}/{{TOTAL}}.
- **Segments where LightGBM wins:** {{TOTAL_MINUS_WON}}.
- **Notes per segment:** {{PER_CLUSTER_NOTES}}

## 4. Recommendation

- **Use intermittent models for:** {{RECOMMEND_INTERMITTENT_SEGMENTS}}.
- **Keep LightGBM for:** {{RECOMMEND_LIGHTGBM_SEGMENTS}}.
- **Bias watch:** {{BIAS_NOTES}} (positive ME = under-forecasting; Croston is known
  to over-forecast, SBA corrects this).

## 5. Caveats

- Croston-family models are **inherently local** (one fit per series); "global vs
  cluster" changes *scoring & selection*, not pooling.
- Comparison is on identical `[unique_id, ds]` backtest windows (inner join).
- `statsforecast` was added as a new dependency for this analysis.

## 6. Reproduce

```python
from forecast_intermittent import (
    build_models, forecast_global, forecast_by_cluster,
    evaluate_forecasts, select_best, compare_to_baseline, narrate_comparison,
)

models = build_models()
cv_global  = forecast_global(df, h={{H}}, freq="{{FREQ}}", models=models, n_windows={{N_WINDOWS}})
cv_cluster = forecast_by_cluster(df, h={{H}}, freq="{{FREQ}}", group_col="profile_cluster",
                                 models=models, n_windows={{N_WINDOWS}})

res_global  = compare_to_baseline(cv_global,  forecasts_df)
res_cluster = compare_to_baseline(cv_cluster, forecasts_df, group_by="profile_cluster")
```
