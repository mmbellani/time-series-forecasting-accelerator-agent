# Chronos-2

**Category:** Alternative model · **Location:** `.github/skills/` · **Extra dependency:** `chronos` / foundation-model runtime

## What it does

Forecasts with a **pretrained time series foundation model**, zero-shot.

## When to use it

When you want cross-learning across series without training a model.

## How it is benchmarked

The model runs **globally** (whole panel) and **per `profile_cluster`**, then is compared with the LightGBM `y_hat_*` baseline from notebook 06 on **MAE, RMSE, WMAPE and ME**, using identical backtest windows.

## Inputs & outputs

| | |
|---|---|
| **Reads** | Pipeline outputs: `profile_cluster` and/or `<scenario>_forecasts` |
| **Writes** | Its own results — the core notebooks are never modified |

!!! note
    See the skill's `SKILL.md` in `.github/skills/` for parameters and usage.

[:octicons-arrow-left-24: Back to Skills Overview](index.md)
