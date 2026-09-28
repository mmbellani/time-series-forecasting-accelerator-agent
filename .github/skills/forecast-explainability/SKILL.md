---
name: forecast-explainability
description: "Explain time-series forecast results and analyze the feature weights (model importances) that drive them. USE FOR: explain forecast, why did the forecast go up/down, interpret model, feature importance, feature weights, which features matter, gain vs split importance, SHAP values, per-cluster feature importance, explain a single prediction, forecast contribution breakdown, model interpretability, translate model weights into a business narrative. Built for the LightGBM + mlforecast pipeline (notebooks 05 Feature Engineering and 06 Train/Tune) that produces per-cluster LGBMRegressor models and <scenario>_forecasts tables. DO NOT USE FOR: training or tuning models (use notebook 06), feature engineering (use notebook 05), data cleaning (use notebook 01), or clustering (use notebook 04)."
license: MIT
metadata:
  author: Time Series Forecasting Accelerator
  version: "1.0.0"
---

# Forecast Explainability Skill

This skill helps you **explain forecast results** and **analyze the feature weights** that drive
a trained forecasting model. It turns raw LightGBM importances and SHAP contributions into a
clear, business-readable narrative, and reconciles *why* a specific forecast point moved.

It is designed for the Time Series Forecasting Accelerator pipeline, where:

- Features are engineered in **notebook 05** (`mlforecast`): calendar features (`year`, `month`,
  `week`), lag features (`lag1`, `lag2`, …), rolling statistics (`RollingMean`, `RollingStd`),
  static per-series features, and encoded categorical features.
- Models are trained in **notebook 06**: one `LGBMRegressor` per cluster, wrapped by
  `mlforecast`. Feature importances are read via `booster.feature_importances_` and
  `booster.feature_name_`.
- Outputs land in Lakehouse tables such as `<scenario>_features`, `<scenario>_forecasts`, and
  `<scenario>_clustered`.

## When To Use

| You want to… | This skill provides |
|--------------|---------------------|
| Understand which features drive a model | `feature_importance()` (gain + split), grouped by feature family |
| Explain a single forecast point | `explain_prediction()` — SHAP contributions with a plain-language summary |
| Compare drivers across clusters | `importance_by_cluster()` |
| Produce a stakeholder report | Templates in `templates/` |
| Translate weights into business language | `narrate_importance()` / `narrate_prediction()` |

## Core Concepts

### Importance types

- **Gain importance** (recommended default): total reduction in loss contributed by a feature
  across all splits. Best proxy for "how much does this feature help accuracy".
- **Split importance**: number of times a feature is used to split. Useful for spotting
  frequently-used-but-low-impact features.

Always report **gain** as the headline and use split as a secondary signal. Never present raw
counts as if they were percentage contributions.

### Feature families

Group features into families so the story is legible:

| Family | Pattern examples | Business meaning |
|--------|------------------|------------------|
| `lag` | `lag1`, `lag2`, `lag12` | Recent history / autocorrelation |
| `rolling` | `rolling_mean_*`, `rolling_std_*` | Short-term trend & volatility |
| `calendar` | `year`, `month`, `week`, `quarter` | Seasonality & time trend |
| `static` | region, segment, product attributes | Series identity / cross-sectional effects |
| `categorical` | encoded category codes | Group-level shifts |
| `exog` | promotions, holidays, price | External drivers |

### SHAP vs. global importance

- **Global importance** (gain/split) answers: *"Which features matter to the model overall?"*
- **SHAP** answers: *"Why is THIS forecast value what it is?"* — additive per-feature
  contributions relative to a baseline (`expected_value`). SHAP contributions sum to the
  prediction, which is what makes single-forecast explanations trustworthy.

## Workflow

1. **Locate the trained model.** In notebook 06, each cluster's booster is available as
   `mlf.models_['LGBMRegressor']` (or the tuned equivalent). Pass the underlying LightGBM
   booster/estimator and the `feature_cols` list to this skill.
2. **Compute global importance.** Call `feature_importance(model, feature_cols)` to get a tidy
   DataFrame with gain %, split %, and family grouping.
3. **Explain specific points.** For any row in `<scenario>_forecasts`, retrieve the corresponding
   feature vector from `<scenario>_features` and call `explain_prediction(model, X_row)`.
4. **Aggregate by cluster (optional).** Loop over per-cluster models and call
   `importance_by_cluster()` to see how drivers differ across segments.
5. **Narrate.** Use `narrate_importance()` / `narrate_prediction()` to generate prose, then drop
   it into a report from `templates/`.

## Usage

```python
from explain import (
    feature_importance,
    explain_prediction,
    importance_by_cluster,
    narrate_importance,
    narrate_prediction,
)

# 1) Global feature weights (from a trained per-cluster LGBMRegressor)
booster = mlf.models_["LGBMRegressor"]          # notebook 06
feature_cols = [c for c in df.columns if c not in [unique_id, date_var, y]]

imp = feature_importance(booster, feature_cols)  # tidy DataFrame
print(narrate_importance(imp, top_n=8))

# 2) Explain one forecast point
X_row = features_df.loc[[row_index], feature_cols]   # single row, same columns as training
contrib = explain_prediction(booster, X_row, feature_cols)
print(narrate_prediction(contrib))

# 3) Drivers per cluster
per_cluster = {cid: mdl for cid, mdl in cluster_models.items()}
cluster_imp = importance_by_cluster(per_cluster, feature_cols)
```

## Boundaries

- ✅ Read model objects and feature tables; compute importances and SHAP; generate narratives.
- ✅ Handle both `LGBMRegressor` estimators and raw `Booster` objects, and any scikit-learn
  estimator that exposes `feature_importances_`.
- ⚠️ SHAP is optional. If `shap` is not installed, `explain_prediction()` falls back to LightGBM's
  built-in `pred_contrib` (which returns the same additive decomposition for tree models).
- 🚫 Do not retrain, re-tune, or overwrite models. This skill is read-only with respect to models
  and data.
- 🚫 Do not invent feature meanings — map families from the actual `feature_cols` and confirm
  business semantics of `static`/`exog` features with the user before asserting causality.

## Files

| File | Purpose |
|------|---------|
| `explain.py` | Core functions: importance extraction, SHAP explanation, family grouping, narrative generation. |
| `templates/feature_importance_report.md` | Stakeholder-ready global importance report. |
| `templates/single_forecast_explanation.md` | Per-forecast explanation write-up. |
| `templates/example_usage.py` | End-to-end runnable example against the pipeline outputs. |
