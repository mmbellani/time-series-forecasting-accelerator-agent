# Moving-Average Forecast Benchmark — {{SCENARIO}}

_Generated: {{DATE}} · Horizon (h): {{H}} · Frequency: {{FREQ}} · Season length: {{SEASON_LENGTH}} · Backtest windows: {{N_WINDOWS}}_

## 1. Summary

- **Series scope:** {{N_SERIES}} series across {{N_CLUSTERS}} `profile_cluster`
  segments (from notebooks 03/04).
- **Models evaluated:** {{MODEL_LIST}} (window-average family) vs the LightGBM
  baseline ({{BASELINE_COLS}}) from notebook 06.
- **Headline result:** {{ONE_LINE_VERDICT}}

> Metrics are scale-free / robust: **MAE**, **RMSE**, **WMAPE**, **ME** (bias).
> `ME > 0` means under-forecasting; moving averages lag trends, so watch the bias.

## 2. Global run (entire panel)

All series scored together; one winning moving-average configuration for the
whole dataset.

| Model | Family | MAE | RMSE | WMAPE (%) | ME (bias) | n |
|-------|--------|-----|------|-----------|-----------|---|
| {{...rows from res_global["metrics"]...}} | | | | | | |

- **Best overall:** {{GLOBAL_WINNER}} ({{GLOBAL_WINNER_FAMILY}}).
- **Moving average vs LightGBM:** {{GLOBAL_DELTA_NARRATIVE}}

## 3. By `profile_cluster`

Each cluster scored on its own; the winning window size may differ per segment
(short windows track fast-moving segments; longer/seasonal windows suit stable
ones).

| profile_cluster | Best model | Family | MAE | RMSE | WMAPE (%) | ME |
|-----------------|-----------|--------|-----|------|-----------|----|
| {{...rows from select_best(..., group_by="profile_cluster")...}} | | | | | | |

- **Segments where moving-average models win:** {{WON}}/{{TOTAL}}.
- **Segments where LightGBM wins:** {{TOTAL_MINUS_WON}}.
- **Notes per segment:** {{PER_CLUSTER_NOTES}}

## 4. Recommendation

- **Use moving-average models for:** {{RECOMMEND_MA_SEGMENTS}} (typically stable,
  low-trend, or strongly seasonal segments).
- **Keep LightGBM for:** {{RECOMMEND_LIGHTGBM_SEGMENTS}}.
- **Bias watch:** {{BIAS_NOTES}} (positive ME = under-forecasting; a moving average
  systematically lags an upward trend).

## 5. Caveats

- Moving-average models are **inherently local** (one fit per series); "global vs
  cluster" changes *scoring & selection*, not pooling.
- Moving averages cannot extrapolate trend and will lag turning points.
- Comparison is on identical `[unique_id, ds]` backtest windows (inner join).
- `statsforecast` was added as a new dependency for this analysis.

## 6. Reproduce

```python
from forecasting_moving_average import (
    build_models, forecast_global, forecast_by_cluster,
    evaluate_forecasts, select_best, compare_to_baseline, narrate_comparison,
)

models = build_models(season_length={{SEASON_LENGTH}})
cv_global  = forecast_global(df, h={{H}}, freq="{{FREQ}}", models=models, n_windows={{N_WINDOWS}})
cv_cluster = forecast_by_cluster(df, h={{H}}, freq="{{FREQ}}", group_col="profile_cluster",
                                 models=models, n_windows={{N_WINDOWS}})

res_global  = compare_to_baseline(cv_global,  forecasts_df)
res_cluster = compare_to_baseline(cv_cluster, forecasts_df, group_by="profile_cluster")
```
