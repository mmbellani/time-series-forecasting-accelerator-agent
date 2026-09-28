"""End-to-end example: explain forecast results and analyze feature weights.

Run this after notebook 06 has trained per-cluster LGBMRegressor models and written
the `<scenario>_features` and `<scenario>_forecasts` tables. It demonstrates the full
forecast-explainability workflow.

Two paths are shown:
  A) Inside a Fabric/Databricks notebook, reusing the in-memory `mlf` model and DataFrames.
  B) Standalone, loading tables from the Lakehouse via Spark.

Adjust SCENARIO, table names, and column names to your run.
"""

# --- make the skill importable when running as a script ---------------------
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))  # skills/forecast-explainability

import pandas as pd

from explain import (
    feature_importance,
    family_importance,
    importance_by_cluster,
    explain_prediction,
    narrate_importance,
    narrate_prediction,
)

# ---------------------------------------------------------------------------
# Configuration — edit for your scenario
# ---------------------------------------------------------------------------
SCENARIO = "revenue_pnl"
UNIQUE_ID = "unique_id"
DATE_VAR = "ds"
TARGET = "y"
UNIT = "USD"

# ===========================================================================
# PATH A — inside the notebook (objects already in memory)
# ===========================================================================
# `mlf`        : the fitted mlforecast object from notebook 06
# `df`         : the engineered feature frame (from <scenario>_features)
# `cluster_models` : optional dict {cluster_id: fitted LGBMRegressor}

def run_in_notebook(mlf, df, cluster_models=None):
    feature_cols = [c for c in df.columns if c not in [UNIQUE_ID, DATE_VAR, TARGET]]
    booster = mlf.models_["LGBMRegressor"]

    # 1) Global feature weights
    imp = feature_importance(booster, feature_cols)
    print("=== Global feature importance (top 15) ===")
    print(imp.head(15).to_string(index=False))
    print("\n=== By family ===")
    print(family_importance(imp).to_string(index=False))
    print("\n=== Narrative ===")
    print(narrate_importance(imp, top_n=8))

    # 2) Explain a single forecast point
    row_index = df.index[-1]  # pick any row you want to explain
    X_row = df.loc[[row_index], feature_cols]
    explanation = explain_prediction(booster, X_row, feature_cols)
    print("\n=== Single forecast explanation ===")
    print(narrate_prediction(explanation, top_n=5, unit=UNIT))

    # 3) Drivers per cluster (optional)
    if cluster_models:
        cluster_imp = importance_by_cluster(cluster_models, feature_cols, top_n=5)
        print("\n=== Top drivers per cluster ===")
        print(cluster_imp.to_string(index=False))

    return imp, explanation


# ===========================================================================
# PATH B — standalone, load features from the Lakehouse
# ===========================================================================

def run_standalone(spark, model):
    """`model` is a re-loaded LightGBM booster/estimator; `spark` an active session."""
    features_df = spark.table(f"{SCENARIO}_features").toPandas()
    feature_cols = [c for c in features_df.columns if c not in [UNIQUE_ID, DATE_VAR, TARGET]]

    imp = feature_importance(model, feature_cols)
    print(narrate_importance(imp, top_n=8))

    X_row = features_df.loc[[0], feature_cols]
    explanation = explain_prediction(model, X_row, feature_cols)
    print(narrate_prediction(explanation, unit=UNIT))
    return imp, explanation


if __name__ == "__main__":
    print(
        "This is a template. Import run_in_notebook / run_standalone into your "
        "notebook, or adapt the configuration block and call one of them with your "
        "trained model and feature DataFrame."
    )
