# 04 · Clustering

**Purpose:** group similar *regular* series so one model can be trained per group — more efficient and more robust than one model per series.

## What it does

- Uses the profiles from [03 · Profiling](03-profiling.md)
- Clusters regular series with **Euclidean K-Means**
- Writes a `profile_cluster` label for every series
- Feeds per-cluster training in [06 · Train / Test / Select / Tune](06-train-tune.md)

!!! tip "Shape-based alternative"
    The [DTW Clustering](../skills/clustering-dtw.md) skill clusters series by *shape* using Dynamic Time Warping, with the same output contract — a drop-in replacement.
