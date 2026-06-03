# Time Series Forecasting Accelerator Agent

A production-ready pipeline for forecasting multiple time series on **Microsoft Fabric**.

**IMPORTANT** If you need to run a local demo without Fabric, please refer to README for DEMO.md

## What It Does

- **Profiles** time series to identify forecastable vs problematic patterns
- **Clusters** similar series for efficient modeling
- **Engineers features** (lags, rolling stats, calendar effects)
- **Trains & tunes** ML models (LightGBM/XGBoost via MLForecast)

## Quick Start

1. Upload your data to a Fabric Lakehouse
2. Run notebooks 01 → 05 in sequence
3. Get forecasts!

## Pipeline

See [Pipeline Overview](docs/migration/00_Pipeline_Overview.md) for detailed documentation.

```
Raw Data → [01] Prep → [02] Profile → [03] Cluster → [04] Features → [05] Train
```

## Notebooks

| # | Notebook | Purpose |
|---|----------|---------|
| 01 | Data Preparation | Clean data, fill time gaps |
| 02 | Profiling | Classify series (regular, lumpy, erratic, etc.) |
| 03 | Clustering | Group similar series with K-Means |
| 04 | Feature Engineering | Create lags, rolling stats, calendar features |
| 05 | Train/Tune | Train LightGBM, tune with Optuna |

## Requirements

- Microsoft Fabric workspace with Lakehouse
- Python packages: `mlforecast`, `lightgbm`, `optuna`, `xgboost`


