# Moving Average

**Category:** Alternative model · **Location:** `.github/skills/` · **Extra dependency:** `statsforecast>=1.7.0`

## What it does

Forecasts with a rolling or seasonal window average.

## When to use it

Smooth, stable or seasonal series where a simple, transparent benchmark is valuable.

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
