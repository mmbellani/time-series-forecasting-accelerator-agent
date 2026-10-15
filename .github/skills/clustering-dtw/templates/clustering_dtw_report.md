# DTW Clustering Report — {{SCENARIO}}

_Generated: {{DATE}} · Metric: {{METRIC}} · Sakoe-Chiba radius: {{SAKOE_CHIBA_RADIUS}} · Winsor limits: {{WINSOR_LIMITS}}_

**Save as:** `{{OUTPUT_FOLDER}}/clustering_interpretation/regular_cluster_interpretation.md`
**Review status:** {{DRAFT_REVIEWED_PARTIAL_BLOCKED_OR_NOT_APPLICABLE}}
**Data source / notebook:** {{DATA_SOURCE}} / {{SOURCE_PREFIXED_NOTEBOOK_NAME}}
**Input / membership artifacts:** {{INPUT_LOCATION}} / {{CLUSTER_MEMBERSHIP_LOCATION}}
**Analysis window / frequency / units:** {{START_DATE}} to {{END_DATE}} / {{FREQUENCY}} / {{UNITS}}

## Business context and checkpoint record

**Known context:** {{SCENARIO_EDA_AND_PRIOR_CHECKPOINT_CONTEXT}}
**Confirmed context:** {{ENTITY_MEANING_GEOGRAPHY_SEGMENTS_CALENDAR_OPERATIONS}}
**Unknowns and limitations:** {{MISSING_CONTEXT_AND_DATA_LIMITATIONS}}
**Decision this interpretation supports:** {{BUSINESS_DECISION}}

| Checkpoint | Questions asked | Data-scientist answers / decisions | Status |
|------------|-----------------|-----------------------------------|--------|
| 4.4-context | {{TARGETED_CONTEXT_QUESTIONS}} | {{ANSWERS}} | {{STATUS}} |
| 4.4-review | {{PER_CLUSTER_REVIEW_QUESTIONS}} | {{DECISIONS}} | {{STATUS}} |

**Completion-report checkpoint references:** {{CHECKPOINT_LINKS_OR_STANDALONE}}

> Ask only unresolved questions, one at a time. Save this report as Draft before the
> review checkpoint. Do not invent answers or mark an unreviewed interpretation accepted.
> If no regular series exist or clustering is skipped, state Not applicable with the
> reason and observed profile counts; omit inapplicable cluster/model sections.

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

### Interpretation overview (every regular cluster)

| Cluster ID | Regular series (n, %) | Observed pattern | Proposed business interpretation | Confidence / rationale | Review status |
|------------|-----------------------|------------------|----------------------------------|------------------------|---------------|
| {{CLUSTER_ID}} | {{N_AND_SHARE}} | {{MEASURED_PATTERN}} | {{HYPOTHESIS_OR_NEUTRAL_LABEL}} | {{CONFIDENCE_AND_EVIDENCE}} | {{DRAFT_ACCEPTED_REVISED_OR_UNRESOLVED}} |

### Cluster {{CLUSTER_ID}}: {{PROPOSED_LABEL}}

<!-- Repeat this entire section for every actual regular cluster, not just the largest. -->

- **Membership and coverage:** {{N_SERIES_SHARE_DATE_RANGE_AND_MISSINGNESS}}
- **Representative members and selection method:** {{SERIES_IDS_AND_SELECTION_RULE}}
- **Observed shape:** {{TREND_SEASONALITY_PEAKS_TROUGHS_AND_WITHIN_CLUSTER_VARIATION}}
- **Original-unit magnitude:** {{LEVEL_AND_SPREAD_NOT_FROM_STANDARDIZED_CENTROIDS}}
- **Verified metadata composition:** {{SEGMENT_COUNTS_SHARES_OR_UNAVAILABLE}}

| Evidence / comparison | Measurement | Baseline / period | Sample counts / repeated events | Caveats |
|-----------------------|-------------|-------------------|--------------------------------|---------|
| {{CALENDAR_OR_SEGMENT_PATTERN}} | {{VALUE_AND_UNITS}} | {{EXPLICIT_BASELINE}} | {{COUNTS}} | {{LIMITATIONS}} |

![Representative members on original dates]({{RELATIVE_MEMBER_CHART_PATH}})
![Calendar pattern at the observed frequency]({{RELATIVE_CALENDAR_CHART_PATH}})

**Interpretation:** {{BUSINESS_HYPOTHESIS_SEPARATE_FROM_OBSERVATIONS}}

**Supporting confirmed context:** {{DATA_SCIENTIST_ANSWERS_OR_METADATA}}

**Alternative explanations / counterexamples:** {{HETEROGENEITY_AND_COMPETING_EXPLANATIONS}}

**Confidence and limitations:** {{RATIONALE_AND_MISSING_EVIDENCE}}

**Open clarifying questions:** {{TARGETED_QUESTIONS_OR_NONE}}

**Potential forecasting implications (recommendations only):** {{FEATURE_OR_SEGMENT_IDEAS}}

**Data-scientist review:** {{ACCEPTED_REVISED_OR_UNRESOLVED_WITH_CORRECTIONS_AND_DATE}}

> Business labels do not change cluster IDs or `profile_cluster`. DTW warping may
> align different calendar dates; verify holiday claims on original timestamps.
> Standardized/winsorized shapes cannot establish volume, event extremes, or customer
> identity. Observations and user acceptance do not prove causality.

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
