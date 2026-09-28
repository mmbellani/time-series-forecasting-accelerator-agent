# Skill · Chronos-2 Foundation Model

**Folder:** `.github/skills/forecasting-chronos2/`
**Runs after:** [03/04 profiling + clustering](Pipeline-Overview) and [06 Train / Tune](06-Train-Test-Select-Tune)

## What it does

Forecasts with a **pretrained time-series foundation model (Chronos-2)** in **zero-shot** mode (no training/fitting) and benchmarks it against the LightGBM baseline.

Runs **twice**:
1. **Globally** — over the entire panel; all series cross-learn via group attention.
2. **By `profile_cluster`** — in-context learning confined to each cluster.

Both are compared (MAE/RMSE/WMAPE/ME) to the notebook-06 `y_hat_*` baseline.

## Why a foundation model

- **Zero-shot** — no training loop; forecasts come from a pretrained model.
- **In-context / cross-learning** — series inform each other via group attention.
- A strong, quick **baseline benchmark** against the tuned gradient-boosting pipeline.

## Metrics

**MAE**, **RMSE**, **WMAPE**, **ME** (bias), per scope, with a per-cluster winner (Chronos vs LightGBM).

## Notes

- **Dependency:** a Chronos-2 runtime / model weights (e.g. `amazon/chronos-2`), not in `requirements.txt`.
- Global vs per-cluster reveals whether cross-learning across all series helps or hurts specific segments.

## Files

- `forecasting_chronos2.py` · templates
