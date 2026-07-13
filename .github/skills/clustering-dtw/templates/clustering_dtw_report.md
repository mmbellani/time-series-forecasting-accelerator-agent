# DTW Clustering Report — {{SCENARIO}}

_Generated: {{DATE}} · Metric: {{METRIC}} · Sakoe-Chiba radius: {{SAKOE_CHIBA_RADIUS}} · Winsor limits: {{WINSOR_LIMITS}}_

## 1. Summary

- **Method:** Dynamic Time Warping (DTW) clustering via `tslearn`
  `TimeSeriesKMeans` — a shape-based, phase-shift-tolerant alternative to the
  Euclidean K-Means in notebook 04.
- **Scope:** {{N_REGULAR}} `regular` (smooth) series clustered; all other profiles
  ({{OTHER_PROFILES}}) kept their original label.
- **Chosen k:** {{CHOSEN_K}} (elbow k = {{ELBOW_K}}, DTW-silhouette k = {{SILHOUETTE_K}}).
- **Headline result:** {{ONE_LINE_VERDICT}}

> DTW aligns series by elastically warping the time axis, so it groups series by
> **shape/pattern** rather than exact timing. Prefer it when drivers (promotions,
> holidays, weather) hit series at slightly different times.

## 2. Choosing the number of clusters

Both diagnostics are computed **under the DTW metric** (not Euclidean), consistent
with how the series were clustered.

| k | Inertia (within-cluster DTW) | DTW silhouette |
|---|------------------------------|----------------|
| {{...rows from choose_n_clusters diagnostics...}} | | |

- **Elbow (kneed):** {{ELBOW_K}}
- **Best DTW silhouette:** {{SILHOUETTE_K}}
- **Suggested k (max of the two, per notebook 04):** {{CHOSEN_K}}
- **Confirmed with data scientist at checkpoint:** {{CHECKPOINT_DECISION}}

## 3. Cluster sizes

| profile_cluster | n_series |
|-----------------|----------|
| {{...rows from cluster_summary(...)...}} | |

- **Total regular series clustered:** {{N_REGULAR}}
- **Notes on cluster shapes / potential drivers:** {{SHAPE_NOTES}}

## 4. Output contract

The saved table (`{{OUTPUT_TABLE}}`) is `df_profiling` plus a single string
**`profile_cluster`** column:

- regular series → their DTW cluster id (`"0"`, `"1"`, …),
- every other profile → its original label ({{OTHER_PROFILES}}).

This is **identical** to the notebook-04 schema, so notebooks 05 (feature
engineering) and 06 (train/tune) require no changes.

## 5. DTW vs Euclidean K-Means (optional)

If a Euclidean baseline was run for comparison:

- **Series that moved cluster under DTW:** {{N_MOVED}} / {{N_REGULAR}}.
- **Interpretation:** {{DTW_VS_EUCLIDEAN_NOTES}} (DTW typically merges same-shape,
  time-shifted series that Euclidean split apart).

## 6. Caveats

- DTW is `O(n²)` per pairwise comparison — far heavier than Euclidean K-Means. A
  Sakoe-Chiba band ({{SAKOE_CHIBA_RADIUS}}) was used to bound the warp window.
- Only **regular** series are clustered; intermittent/lumpy/erratic/unforecastable
  series keep their profile label.
- `tslearn` was added as a new dependency for this analysis.

## 7. Reproduce

```python
from clustering_dtw import (
    filter_regular_series, build_series_matrix, choose_n_clusters,
    fit_dtw_clusters, assign_profile_cluster, cluster_summary, narrate_clusters,
)

df_reg, ids = filter_regular_series(df_final, df_profiling, unique_id="{{UNIQUE_ID}}")
X, ids, wide = build_series_matrix(df_reg, "{{UNIQUE_ID}}", "{{DATE_VAR}}", "{{TARGET}}")

diag = choose_n_clusters(X, k_range=range(2, 8), metric="{{METRIC}}",
                         sakoe_chiba_radius={{SAKOE_CHIBA_RADIUS}})
labels_df, model = fit_dtw_clusters(X, ids, n_clusters=diag["suggested_k"],
                                    unique_id="{{UNIQUE_ID}}", metric="{{METRIC}}",
                                    sakoe_chiba_radius={{SAKOE_CHIBA_RADIUS}})
df_clustered = assign_profile_cluster(df_profiling, labels_df, unique_id="{{UNIQUE_ID}}")
```
