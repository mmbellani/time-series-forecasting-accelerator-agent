# Getting Started

## Overview

This project is the **Time Series Forecasting Accelerator Agent**. It ships a 6-notebook pipeline that cleans data, profiles each series, clusters similar series, engineers features, and trains per-cluster **LightGBM** models via `mlforecast`, plus a library of pluggable [skills](Skills-Overview) for alternative models and diagnostics.

## Repository layout

```
databricks.yml                 # Databricks Asset Bundle config
requirements.txt               # Python dependencies
docs/                          # Design docs
src/notebooks/                 # The 6-notebook pipeline (+ templates/)
.github/skills/                # Pluggable analysis & benchmarking skills
.github/agents/                # time-series-forecaster agent definition
wiki/                          # This documentation (publishable to GitHub Wiki)
```

## Environment

- **Runtime:** Microsoft Fabric or Databricks (Spark-based). Notebooks read/write tables via Spark and fall back to local Parquet.
- **Python deps:** install from `requirements.txt`. Some skills need extra packages not yet in it (flagged per skill): `tslearn` (DTW clustering), `statsforecast` (moving-average / intermittent), `prophet`, `chronos`.

```bash
pip install -r requirements.txt
```

## Data expectations

The pipeline works on **panel (long) data** — one row per series per date:

| Concept | Example column | Notes |
|---------|----------------|-------|
| Series id | `unique_id` / `STORE_LOCATION_ID` | identifies each time series |
| Date | `ds` / `WEEK_START_DT` | timestamp at a fixed frequency |
| Target | `y` / `TOTAL_NET_SALES` | the value to forecast |
| Grouping | `profile_cluster` | added by notebooks 03/04 |

Column names are configurable at the top of each notebook.

## Running the pipeline

Run the notebooks in order — each reads the prior stage's output table:

1. [01 · Data Preparation](01-Data-Preparation)
2. [02 · Exploratory Data Analysis](02-Exploratory-Data-Analysis)
3. [03 · Profiling (Intermittent)](03-Profiling-Intermittent)
4. [04 · Clustering](04-Clustering)
5. [05 · Feature Engineering](05-Feature-Engineering)
6. [06 · Train / Test / Tune](06-Train-Test-Select-Tune)

See [Pipeline Overview](Pipeline-Overview) for the data-flow diagram and table contracts.

## The forecasting agent

The `time-series-forecaster` agent (in `.github/agents/`) customizes this pipeline for a specific dataset through a phased, checkpointed workflow (intake → scenario interpretation → customization planning → per-notebook generation → finalization).
