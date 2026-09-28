# Chronos-2 Foundation-Model Forecast Benchmark — {{SCENARIO}}

_Generated: {{DATE}} · Horizon (h): {{H}} · Frequency: {{FREQ}} · Backtest windows: {{N_WINDOWS}} · Device: {{DEVICE}}_

## 1. Summary

- **Series scope:** {{N_SERIES}} series across {{N_CLUSTERS}} `profile_cluster`
  segments (from notebooks 03/04).
- **Model evaluated:** Chronos-2 (`amazon/chronos-2`, zero-shot foundation model)
  {{EXTRA_MODELS}} vs the LightGBM baseline ({{BASELINE_COLS}}) from notebook 06.
- **Headline result:** {{ONE_LINE_VERDICT}}

> Metrics are robust / scale-free: **MAE**, **RMSE**, **WMAPE**, **ME** (bias).
> MAPE is omitted — undefined on zero-value periods.

## 2. Global run (entire panel)

All series passed to Chronos-2 in one call, so the model cross-learns across the
whole dataset via group attention; one winning model for the whole dataset.

| Model | Family | MAE | RMSE | WMAPE (%) | ME (bias) | n |
|-------|--------|-----|------|-----------|-----------|---|
| {{...rows from res_global["metrics"]...}} | | | | | | |

- **Best overall:** {{GLOBAL_WINNER}} ({{GLOBAL_WINNER_FAMILY}}).
- **Chronos-2 vs LightGBM:** {{GLOBAL_DELTA_NARRATIVE}}

## 3. By `profile_cluster`

Chronos-2 called once per cluster; in-context learning is confined to each
segment. The winner may differ per cluster.

| profile_cluster | Best model | Family | MAE | RMSE | WMAPE (%) | ME |
|-----------------|-----------|--------|-----|------|-----------|----|
| {{...rows from select_best(..., group_by="profile_cluster")...}} | | | | | | |

- **Segments where Chronos-2 wins:** {{WON}}/{{TOTAL}}.
- **Segments where LightGBM wins:** {{TOTAL_MINUS_WON}}.
- **Global vs per-cluster:** {{GLOBAL_VS_CLUSTER_NOTES}} (does confining
  cross-learning to a cluster help or hurt?).

## 4. Recommendation

- **Use Chronos-2 for:** {{RECOMMEND_CHRONOS_SEGMENTS}}.
- **Keep LightGBM for:** {{RECOMMEND_LIGHTGBM_SEGMENTS}}.
- **Bias watch:** {{BIAS_NOTES}} (positive ME = under-forecasting).

## 5. Caveats

- Chronos-2 is **zero-shot** — no per-series fitting; the "backtest" is pure
  rolling-origin inference.
- "Global vs cluster" changes the model's **in-context set** (group attention),
  which genuinely alters the forecasts — not just the scoring scope.
- Comparison is on identical `[unique_id, ds]` backtest windows (inner join).
- Assumes a gap-filled panel (notebook 01) so cutoffs align across series.
- `chronos-forecasting>=2.0` and `torch` were added as new dependencies; model
  weights download from Hugging Face on first use.

## 6. Reproduce

```python
from forecasting_chronos2 import (
    build_models, forecast_global, forecast_by_cluster,
    evaluate_forecasts, select_best, compare_to_baseline, narrate_comparison,
)

models = build_models(model_names=["amazon/chronos-2"], device_map="{{DEVICE}}")
cv_global  = forecast_global(df, h={{H}}, freq="{{FREQ}}", models=models, n_windows={{N_WINDOWS}})
cv_cluster = forecast_by_cluster(df, h={{H}}, freq="{{FREQ}}", group_col="profile_cluster",
                                 models=models, n_windows={{N_WINDOWS}})

res_global  = compare_to_baseline(cv_global,  forecasts_df)
res_cluster = compare_to_baseline(cv_cluster, forecasts_df, group_by="profile_cluster")
```
