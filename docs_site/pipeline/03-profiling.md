# 03 · Profiling

**Purpose:** identify which series are forecastable and which are problematic, so each gets an appropriate approach.

## What it does

- Computes intermittency indicators per series
- Classifies series into demand patterns (e.g. smooth, erratic, intermittent, lumpy, constant)
- Adds profile information used by [Clustering](04-clustering.md)

See [Intermittent Series](../methodology/intermittent.md) for the indicators and thresholds.
