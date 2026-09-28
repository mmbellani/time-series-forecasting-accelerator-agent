# Single Forecast Explanation — {{SCENARIO}}

**Series (`unique_id`):** {{UNIQUE_ID_VALUE}}
**Forecast date (`ds`):** {{FORECAST_DATE}}
**Cluster / segment:** {{CLUSTER}}
**Method:** {{METHOD}} (SHAP / pred_contrib)

---

## Headline

**Forecast value:** {{PREDICTION}} {{UNIT}}
**Model baseline (expected value):** {{BASELINE}} {{UNIT}}
**Net feature effect:** {{NET_EFFECT}} {{UNIT}}

> Auto-fill from `narrate_prediction(explanation, unit="{{UNIT}}")`.

{{NARRATIVE}}

---

## Why the forecast is what it is

The prediction is the baseline plus the sum of per-feature contributions
(additive decomposition — contributions sum exactly to the forecast).

### Pushing the forecast UP

| Feature | Value | Family | Contribution (+) |
|---------|------:|--------|-----------------:|
| {{up_feature_1}} | {{up_value_1}} | {{up_family_1}} | +{{up_contrib_1}} |
| {{up_feature_2}} | {{up_value_2}} | {{up_family_2}} | +{{up_contrib_2}} |
| … | … | … | … |

### Pushing the forecast DOWN

| Feature | Value | Family | Contribution (−) |
|---------|------:|--------|-----------------:|
| {{down_feature_1}} | {{down_value_1}} | {{down_family_1}} | {{down_contrib_1}} |
| {{down_feature_2}} | {{down_value_2}} | {{down_family_2}} | {{down_contrib_2}} |
| … | … | … | … |

*Source:* `explain_prediction(model, X_row, feature_cols)`.

---

## Reconciliation check

`baseline ({{BASELINE}}) + Σ contributions ({{SUM_CONTRIB}}) = prediction ({{PREDICTION}})`

If these do not tie out, the feature vector passed to `explain_prediction` does not match
the row that produced the forecast — re-align columns/order before trusting the story.

---

## Caveats

- Contributions are **local** to this point and may differ from the global importance ranking.
- Lag/rolling contributions reflect the series' own recent behavior, not external actions.
- For volatile / intermittent series, a single point's explanation can be dominated by one lag.
