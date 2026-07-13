# Skill · DTW Clustering

**Folder:** `.github/skills/clustering-dtw/`
**Alternative to:** [04 Clustering](04-Clustering) · **Runs after:** [03 Profiling](03-Profiling-Intermittent) · **Runs before:** [05 Feature Engineering](05-Feature-Engineering)

## What it does

Clusters the **regular/smooth** series by **shape** using **Dynamic Time Warping (DTW)** instead of Euclidean K-Means. It keeps the notebook-04 pipeline shape and output contract exactly, swapping only the distance/assignment step.

| Step | Notebook 04 | This skill |
|------|-------------|------------|
| Filter | `profile == "regular"` | same |
| Winsorize | 5% / 5% | same |
| Standardize | per-series | same (`TimeSeriesScalerMeanVariance`) |
| Choose k | elbow + **Euclidean** silhouette | elbow + **DTW** silhouette |
| **Cluster** | `sklearn` KMeans (Euclidean) | `tslearn` `TimeSeriesKMeans` (DTW) |
| Output | `profile_cluster` | same |

## Why DTW

Euclidean K-Means compares series point-by-point at the same timestamp, so same-shaped but phase-shifted series look far apart. DTW warps the time axis to align by **pattern**, grouping series whose drivers hit at slightly different times.

## Public API

`filter_regular_series` · `build_series_matrix` · `build_dtw_model` · `choose_n_clusters` (elbow + DTW silhouette) · `fit_dtw_clusters` · `assign_profile_cluster` · `cluster_summary` · `narrate_clusters`

## Notes

- **Dependency:** `tslearn>=0.6.3` (not yet in `requirements.txt`).
- **Performance:** DTW is `O(n²)` per pair — pass a `sakoe_chiba_radius` to band the warp window; keep `n_init` low; only regular series are clustered.
- **Checkpoint:** choosing `k` is a stop point — confirm with the data scientist before fitting.
- **Output contract** is identical to notebook 04, so notebooks 05/06 need no changes.

## Files

- `clustering_dtw.py` — core functions
- `templates/example_usage.py` — end-to-end runnable example
- `templates/clustering_dtw_report.md` — stakeholder report
