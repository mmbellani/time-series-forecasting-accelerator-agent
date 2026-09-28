# 06 · Train / Test / Select / Tune

**Notebook:** `src/notebooks/06 TrainTestSelectTune.ipynb`
**Reads:** `<scenario>_features` · **Writes:** `<scenario>_forecasts`

## Purpose

Train per-cluster **LightGBM** models with `mlforecast`, backtest them, select the best per series/cluster, and tune hyperparameters with **Optuna**.

## What it does

1. **Train** `LGBMRegressor` models per `profile_cluster` via `mlforecast`.
2. **Backtest** with rolling-origin cross-validation.
3. **Select** the best-performing model/target transform per series.
4. **Tune** hyperparameters with Optuna.

## Output — the baseline contract

`<scenario>_forecasts` with:

- `unique_id` — series id
- `ds` — date
- `y` — actual value
- one or more `y_hat_*` — predictions (e.g. `y_hat_identity`, `y_hat_std`)
- a selected best model per series/cluster

This table is the **baseline** that the benchmarking and diagnostic [skills](Skills-Overview) consume.

## Related skills

- **Benchmark alternatives:** [Moving Average](Skill-forecasting-moving-average) · [Prophet](Skill-forecasting-prophet) · [Intermittent / Croston](Skill-forecasting-intermittent) · [Chronos-2](Skill-forecasting-chronos2)
- **Diagnose:** [Explainability](Skill-forecast-explainability) · [Error Analysis](Skill-error-analysis) · [Hierarchical Reconciliation](Skill-hierarchical-reconciliation)
