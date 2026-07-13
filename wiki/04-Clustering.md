# 04 · Clustering

**Notebook:** `src/notebooks/04 Clustering.ipynb`
**Reads:** `<scenario>_profiled` · **Writes:** `<scenario>_clustered`

## Purpose

Group **regular/smooth** series with similar consumption patterns so a tailored model can be built per cluster. Clustering informs the choice of regressors, algorithm, and training window per segment.

## What it does

1. **Filter** to series labelled `regular` (from [03 Profiling](03-Profiling-Intermittent)).
2. **Winsorize** the tails (default 5% / 5%) to limit outlier influence.
3. **Standardize** per series so clustering keys on *shape*, not level/scale.
4. **Build a series × time matrix** with no missing values.
5. **Choose k** with the **elbow method** (inertia + `kneed`) and the **silhouette coefficient**.
6. **Cluster** with `sklearn` **K-Means** (Euclidean distance).
7. **Assign** each regular series a `profile_cluster`; all other profiles keep their label.

## Checkpoints

The notebook stops for the data scientist to confirm the number of clusters to try and the final `k`, and to review sample series per cluster (hints on drivers for feature engineering).

## Output

`<scenario>_clustered` — the profiling table plus a string `profile_cluster` column (cluster id for regular series; original profile label otherwise). Consumed by [05 Feature Engineering](05-Feature-Engineering).

## Alternative

For **shape-based, phase-shift-tolerant** clustering, use the [DTW Clustering skill](Skill-clustering-dtw) as a drop-in alternative that keeps the same output contract.

## Next

→ [05 · Feature Engineering](05-Feature-Engineering)
