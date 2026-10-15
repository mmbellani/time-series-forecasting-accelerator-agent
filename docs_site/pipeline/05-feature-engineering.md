# 05 · Feature Engineering

**Purpose:** Build the inputs the ML models learn from.

## What it does

- Lag features
- Rolling statistics (means, std, …)
- Calendar effects (week, month, holidays)
- Optional external regressors

!!! note
    Column names and parameters are configured at the top of the notebook.

See [Nixtla Framework](../methodology/nixtla.md) for how lags and transforms are declared in `mlforecast`.
