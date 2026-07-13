# Feature Importance Report — {{SCENARIO}}

**Model:** LightGBM (`LGBMRegressor`) via mlforecast
**Generated:** {{DATE}}
**Cluster / segment:** {{CLUSTER_OR_ALL}}
**Forecast horizon:** {{HORIZON}}
**Target:** {{TARGET}} ({{UNIT}})

---

## 1. Executive summary

> One-paragraph, plain-language answer to *"what drives this forecast model?"*
> Auto-fill from `narrate_importance(imp)`.

{{NARRATIVE_SUMMARY}}

---

## 2. Top feature weights (global, gain-based)

Gain importance = total reduction in model loss attributed to each feature.

| Rank | Feature | Family | Gain % | Split % |
|-----:|---------|--------|-------:|--------:|
| 1 | {{feature_1}} | {{family_1}} | {{gain_pct_1}} | {{split_pct_1}} |
| 2 | {{feature_2}} | {{family_2}} | {{gain_pct_2}} | {{split_pct_2}} |
| 3 | {{feature_3}} | {{family_3}} | {{gain_pct_3}} | {{split_pct_3}} |
| … | … | … | … | … |

*Source:* `feature_importance(model, feature_cols)`.

---

## 3. Contribution by feature family

Grouping features into families makes the story legible for stakeholders.

| Family | # Features | Gain % | Business meaning |
|--------|-----------:|-------:|------------------|
| lag | {{n_lag}} | {{gain_lag}} | Recent history / autocorrelation |
| rolling | {{n_rolling}} | {{gain_rolling}} | Short-term trend & volatility |
| calendar | {{n_calendar}} | {{gain_calendar}} | Seasonality & time trend |
| static | {{n_static}} | {{gain_static}} | Series identity / cross-sectional |
| categorical | {{n_categorical}} | {{gain_categorical}} | Group-level shifts |
| exog | {{n_exog}} | {{gain_exog}} | External drivers |

*Source:* `family_importance(imp)`.

---

## 4. Interpretation notes

- **Gain vs. split:** Headline is *gain*. If a feature has high split % but low gain %,
  it is used often but adds little accuracy — flag as a candidate for pruning.
- **Correlation caveat:** Importance is not causation. Lag/rolling features encode the
  series' own momentum, not external levers.
- **Confirm semantics:** Verify the business meaning of `static` and `exog` features
  before asserting cause-and-effect.

---

## 5. Recommended actions

- [ ] Validate that the dominant family matches domain expectation for {{SCENARIO}}.
- [ ] Review low-gain / high-split features for removal in notebook 05.
- [ ] If external drivers should matter but rank low, revisit exogenous feature quality.
