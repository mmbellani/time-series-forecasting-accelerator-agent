# Prophet

**Category:** Alternative model · **Location:** `.github/skills/` · **Extra dependency:** `prophet`

## What it does

Fits an additive model of **trend + seasonality + holidays**.

## When to use it

Series with strong seasonality or holiday effects.

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
