# 02 · Exploratory Data Analysis

**Notebook:** `src/notebooks/02 ExploratoryDataAnalysis.ipynb`
**Reads:** `<scenario>_prepared` · **Writes:** (analysis only)

## Purpose

Understand the data before modelling: distributions, trends, seasonality, and relationships that inform profiling, clustering, and feature engineering.

## What it does

- **Summary statistics** — per-series and aggregate descriptives.
- **Visualizations** — time-series plots, distributions, seasonal views.
- **Feature analysis** — early signal on which calendar/exogenous drivers matter.

## Output

No table is written; the outputs are charts and insights that guide decisions in later stages (e.g. which lags/rolling windows to use in [05 Feature Engineering](05-Feature-Engineering), and which drivers to capture).

## Next

→ [03 · Profiling (Intermittent)](03-Profiling-Intermittent)
