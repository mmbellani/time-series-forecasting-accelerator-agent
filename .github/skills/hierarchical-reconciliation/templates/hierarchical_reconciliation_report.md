# Hierarchical Reconciliation Report — {{SCENARIO}}

**Model:** {{MODEL_NAME}} (LightGBM via mlforecast, notebook 06)
**Generated:** {{DATE}}
**Evaluation window:** {{EVAL_START}} → {{EVAL_END}}
**Target:** {{TARGET}} ({{UNIT}})
**Base series:** {{N_BASE}} • **Reconciliation:** bottom-up

> Run **after** the `forecast-explainability` and `error-analysis` reports. This report
> lifts both to the aggregate: *how base forecasts compose the total* and *how base errors
> propagate up the hierarchy*.

---

## 0. Hierarchy definition (confirmed with the data scientist)

**Levels (top → bottom):** {{LEVELS}}
**Target aggregation level:** {{TARGET_LEVEL}}

| Level | Depth | Parent level | # nodes | Avg children / parent |
|-------|------:|--------------|--------:|----------------------:|
| Total | 0 | - | 1 | 1 |
| {{level_1}} | 1 | Total | {{n_1}} | {{fanout_1}} |
| {{level_2}} | 2 | {{level_1}} | {{n_2}} | {{fanout_2}} |
| {{level_3}} | 3 | {{level_2}} | {{n_3}} | {{fanout_3}} |

![Hierarchy shape](img/{{SCENARIO}}_hierarchy_tree.png)

*Source:* `describe_hierarchy(df, levels)` / `plot_hierarchy_tree(df, levels)`.
**Nesting check:** {{NESTING_NOTES}} *(from `validate_hierarchy`)*.

{{NARRATIVE_HIERARCHY}}  *(from `narrate_hierarchy`)*

---

## 1. Executive summary

> One-paragraph, plain-language answer to *"what builds the aggregate forecast, and where
> does the error come from as it rolls up?"* Auto-fill from `narrate_reconciliation` and
> `narrate_error_propagation`.

{{NARRATIVE_SUMMARY}}

---

## 2. Aggregate fit — how the forecast results in the aggregate

### 2.1 Aggregate actual vs bottom-up forecast

![Aggregate fit](img/{{SCENARIO}}_agg_fit_{{TARGET_LEVEL}}.png)
![Reconciliation grid](img/{{SCENARIO}}_recon_grid.png)

*Source:* `plot_aggregate_actual_vs_forecast(df, levels, "{{TARGET_LEVEL}}")` /
`reconciliation_grid(df, levels)`.

### 2.2 Composition — which nodes build the aggregate

![Contribution bars](img/{{SCENARIO}}_contrib_bars_{{TARGET_LEVEL}}.png)
![Contribution over time](img/{{SCENARIO}}_contrib_area_{{TARGET_LEVEL}}.png)
![Waterfall to aggregate](img/{{SCENARIO}}_waterfall_{{TARGET_LEVEL}}.png)

| Node | Forecast ({{UNIT}}) | Share % | Cum. share % |
|------|--------------------:|--------:|-------------:|
| {{node_1}} | {{val_1}} | {{share_1}} | {{cum_1}} |
| {{node_2}} | {{val_2}} | {{share_2}} | {{cum_2}} |
| {{node_3}} | {{val_3}} | {{share_3}} | {{cum_3}} |
| … | … | … | … |

*Source:* `level_contributions(df, levels, "{{TARGET_LEVEL}}")` /
`plot_contribution_bars` / `plot_level_contributions` / `plot_waterfall`.

{{NARRATIVE_RECONCILIATION}}  *(from `narrate_reconciliation`)*

> **Hand-off:** run `forecast-explainability` (`explain_prediction`) on the top
> contributor(s) above to see which feature weights drive the base forecast that moves the
> aggregate.

---

## 3. Error propagation — where errors are and how they roll up

### 3.1 Error by level (the propagation curve)

![Error by level](img/{{SCENARIO}}_error_by_level.png)

| Level | n | ME | MAE | RMSE | MAPE % | WMAPE % |
|-------|--:|---:|----:|-----:|-------:|--------:|
| Total | {{n}} | {{me}} | {{mae}} | {{rmse}} | {{mape}} | {{wmape}} |
| {{level_1}} | … | … | … | … | … | … |
| {{level_last}} (base) | … | … | … | … | … | … |

*Source:* `error_by_level(df, levels)` / `plot_error_by_level(df, levels)`.

> Falling MAPE/WMAPE from base → Total ⇒ errors **cancel** (noise averages out). A large,
> persistent |ME| ⇒ **systematic bias** that propagates straight up.

### 3.2 How much error cancels on aggregation

| Level | Gross abs error | Net abs error | Cancellation % | Diversification |
|-------|----------------:|--------------:|---------------:|----------------:|
| Total | {{gross}} | {{net}} | {{cancel}} | {{div}} |
| {{level_1}} | … | … | … | … |

*Source:* `error_cancellation(df, levels)`.

> `Cancellation %` = share of gross base error that disappears on aggregation.
> `Diversification` (net/gross): 0 = perfect cancellation, 1 = errors reinforce.

### 3.3 Which nodes drive the aggregate error

![Error propagation waterfall](img/{{SCENARIO}}_error_propagation_{{TARGET_LEVEL}}.png)

| Node | Signed error ({{UNIT}}) | Direction | % of gross error |
|------|------------------------:|-----------|-----------------:|
| {{node_1}} | {{err_1}} | {{dir_1}} | {{grosspct_1}} |
| {{node_2}} | {{err_2}} | {{dir_2}} | {{grosspct_2}} |
| … | … | … | … |

*Source:* `error_contribution(df, levels, "{{TARGET_LEVEL}}")` /
`plot_error_propagation`.

{{NARRATIVE_ERROR_PROPAGATION}}  *(from `narrate_error_propagation`)*

> **Hand-off:** run `error-analysis` (`compute_errors` / `worst_buckets`) on the driver
> node(s) to see *when* they miss, then `forecast-explainability` (`explain_prediction`) on
> those points to see *which feature weights* caused the miss that propagated up.

---

## 4. Coherence (only if a direct aggregate model exists)

If any level was forecast **directly** (not by summing children), report the gap.

| Node | Bottom-up | Direct | Gap (direct − BU) |
|------|----------:|-------:|------------------:|
| {{node_1}} | {{bu_1}} | {{direct_1}} | {{gap_1}} |

*Source:* `coherence_gap(base_df, agg_forecast, levels, "{{TARGET_LEVEL}}")`.

> A large systematic gap means the base and direct models disagree — consider optimal
> (MinT) reconciliation as a follow-up.

---

## 5. Interpretation notes & caveats

- **Composition ≠ cause:** the largest node drives the total *arithmetically*; confirm the
  *why* via `forecast-explainability` before asserting a business cause.
- **Cancellation vs bias:** high cancellation means the aggregate is trustworthy even if
  base series are noisy; low cancellation + large |ME| means correlated bias — fix at the
  base (features/model in notebooks 05/06).
- **MAPE instability:** unreliable near-zero aggregates — read WMAPE instead.
- **Nesting:** grouped (non-strictly-nested) dimensions are valid but interpret shares per
  grouping, not as a strict tree.

---

## 6. Recommended actions

- [ ] Explain the top aggregate contributor(s) with `forecast-explainability`.
- [ ] Root-cause the top error-driver node(s) with `error-analysis`.
- [ ] If aggregate bias (|ME|) is high with low cancellation, add/adjust bias correction
      at the base in notebook 06.
- [ ] If a direct aggregate model disagrees, evaluate MinT reconciliation.
- [ ] Re-run this report after changes and compare the error-by-level curve.
