# Prophet Forecast Benchmark — {{SCENARIO}}

_Generated: {{DATE}} · Horizon (h): {{H}} · Frequency: {{FREQ}} · Backtest windows: {{N_WINDOWS}}_

## 1. Summary

- **Series scope:** {{N_SERIES}} series across {{N_CLUSTERS}} `profile_cluster`
  segments (from notebooks 03/04).
- **Models evaluated:** {{MODEL_LIST}} (Prophet configurations) vs the LightGBM
  baseline ({{BASELINE_COLS}}) from notebook 06.
- **Headline result:** {{ONE_LINE_VERDICT}}

> Metrics are scale-free / robust: **MAE**, **RMSE**, **WMAPE**, **ME** (bias).
> MAPE is intentionally omitted — undefined on zero-value periods.

## 2. Global run (entire panel)

All series scored together; one winning Prophet configuration for the whole dataset.

| Model | Family | MAE | RMSE | WMAPE (%) | ME (bias) | n |
|-------|--------|-----|------|-----------|-----------|---|
| {{...rows from res_global["metrics"]...}} | | | | | | |

- **Best overall:** {{GLOBAL_WINNER}} ({{GLOBAL_WINNER_FAMILY}}).
- **Prophet vs LightGBM:** {{GLOBAL_DELTA_NARRATIVE}}

## 3. By `profile_cluster`

Each cluster scored on its own; the winning Prophet configuration may differ per
segment (flexible-trend clusters often prefer `Prophet_Flexible`; stable ones prefer
`Prophet_Smooth`).

| profile_cluster | Best model | Family | MAE | RMSE | WMAPE (%) | ME |
|-----------------|-----------|--------|-----|------|-----------|----|
| {{...rows from select_best(..., group_by="profile_cluster")...}} | | | | | | |

- **Segments where Prophet wins:** {{WON}}/{{TOTAL}}.
- **Segments where LightGBM wins:** {{TOTAL_MINUS_WON}}.
- **Notes per segment:** {{PER_CLUSTER_NOTES}}

## 4. Recommendation

- **Use Prophet for:** {{RECOMMEND_PROPHET_SEGMENTS}}.
- **Keep LightGBM for:** {{RECOMMEND_LIGHTGBM_SEGMENTS}}.
- **Bias watch:** {{BIAS_NOTES}} (positive ME = under-forecasting; check
  `seasonality_mode` and `changepoint_prior_scale` if a config consistently biases).

## 5. Caveats

- Prophet is **inherently local** (one fit per series); "global vs cluster" changes
  *scoring & selection*, not pooling.
- Comparison is on identical `[unique_id, ds]` backtest windows (inner join).
- Prophet fits one model per series per window, so runtime scales with series ×
  windows × configurations.
- `prophet` was added as a new dependency for this analysis (compiles a Stan backend
  on first use).

## 6. Reproduce

```python
from forecasting_prophet import (
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
