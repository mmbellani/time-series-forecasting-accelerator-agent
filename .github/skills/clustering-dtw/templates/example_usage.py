"""End-to-end example: DTW clustering of regular time series (alternative to notebook 04).

Run this AFTER notebook 03 (profiling) has produced the `profile` label for each
series, and BEFORE notebook 05 (feature engineering), which consumes
`profile_cluster`.

This reproduces the notebook-04 pipeline exactly — filter to the `regular`
(smooth) profiles, winsorize, standardize, choose k, cluster, and write a
`profile_cluster` column — but swaps Euclidean K-Means for DTW-based
`TimeSeriesKMeans` so series are grouped by SHAPE rather than exact timing.

Two paths are shown:
  A) Inside a Fabric/Databricks notebook, reusing in-memory DataFrames.
  B) Standalone, loading tables from the Lakehouse / catalog via Spark.

NOTE: `tslearn` is required and is not yet in `requirements.txt`. Install it
first:  pip install "tslearn>=0.6.3"

Adjust SCENARIO, table names, column names, METRIC, and the Sakoe-Chiba radius to
your run.
"""

# --- make the skill importable when running as a script ---------------------
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))  # skills/clustering-dtw

import pandas as pd

from clustering_dtw import (
    filter_regular_series,
    build_series_matrix,
    choose_n_clusters,
    fit_dtw_clusters,
    assign_profile_cluster,
    cluster_summary,
    narrate_clusters,
)

# ---------------------------------------------------------------------------
# Configuration — edit for your scenario
# ---------------------------------------------------------------------------
SCENARIO = "supermarket_net_sales"

# Column names (defaults mirror notebook 04)
UNIQUE_ID = "STORE_LOCATION_ID"
DATE_VAR = "WEEK_START_DT"
TARGET = "TOTAL_NET_SALES"
PROFILE_COL = "profile"
REGULAR_LABEL = "regular"

# DTW clustering controls
METRIC = "dtw"              # "dtw" | "softdtw" | "euclidean"
SAKOE_CHIBA_RADIUS = 5      # band the warp window for speed; None = unconstrained
K_RANGE = range(2, 8)       # candidate cluster counts to sweep
WINSOR_LIMITS = (0.05, 0.05)

# Lakehouse / catalog config (Path B)
LAKEHOUSE_NAME = "ts_forecasting"
INPUT_TABLE = "df_final"
PROFILING_TABLE = "df_profiling"
OUTPUT_TABLE = "df_profiling_clustering"


def run_dtw_clustering(df_final: pd.DataFrame, df_profiling: pd.DataFrame) -> pd.DataFrame:
    """Full DTW clustering flow → returns df_profiling with a `profile_cluster` column."""
    # 1) Restrict to regular/smooth series (all other profiles keep their label).
    df_reg, regular_ids = filter_regular_series(
        df_final, df_profiling,
        unique_id=UNIQUE_ID, profile_col=PROFILE_COL, regular_label=REGULAR_LABEL,
    )
    print(f"Regular series to cluster: {len(regular_ids)}")

    # 2) Winsorize + standardize + dense (n_series, n_timestamps, 1) array.
    X, ids, wide = build_series_matrix(
        df_reg, UNIQUE_ID, DATE_VAR, TARGET, winsor_limits=WINSOR_LIMITS,
    )
    print(f"DTW matrix: {X.shape[0]} series x {X.shape[1]} timestamps")

    # 3) CHECKPOINT — choose k under the DTW metric (elbow + DTW silhouette).
    diag = choose_n_clusters(
        X, k_range=K_RANGE, metric=METRIC, sakoe_chiba_radius=SAKOE_CHIBA_RADIUS,
    )
    print(f"elbow_k={diag['elbow_k']}  silhouette_k={diag['silhouette_k']}  "
          f"suggested_k={diag['suggested_k']}")
    # >>> Present these diagnostics to the data scientist and confirm k before fitting. <<<
    chosen_k = diag["suggested_k"]

    # 4) Fit DTW clustering with the confirmed k.
    labels_df, model = fit_dtw_clusters(
        X, ids, n_clusters=chosen_k, unique_id=UNIQUE_ID,
        metric=METRIC, sakoe_chiba_radius=SAKOE_CHIBA_RADIUS,
    )

    # 5) Reproduce the notebook-04 output contract.
    df_clustered = assign_profile_cluster(
        df_profiling, labels_df,
        unique_id=UNIQUE_ID, profile_col=PROFILE_COL, regular_label=REGULAR_LABEL,
    )

    print(cluster_summary(labels_df, unique_id=UNIQUE_ID))
    print(narrate_clusters(labels_df, diagnostics=diag, metric=METRIC, unique_id=UNIQUE_ID))
    return df_clustered


# ===========================================================================
# PATH A — inside the notebook (objects already in memory)
# ===========================================================================
# `df_final`     : the prepared panel with UNIQUE_ID, DATE_VAR, TARGET.
# `df_profiling` : the profiling table (one row per series) with a `profile` column.
#
# df_profiling_clustering = run_dtw_clustering(df_final, df_profiling)
# df_profiling_clustering.head()


# ===========================================================================
# PATH B — standalone: load tables via Spark, run, and save back
# ===========================================================================
if __name__ == "__main__":
    try:
        df_final = spark.table(f"{LAKEHOUSE_NAME}.{INPUT_TABLE}").toPandas()          # noqa: F821
        df_profiling = spark.table(f"{LAKEHOUSE_NAME}.{PROFILING_TABLE}").toPandas()  # noqa: F821
    except Exception as exc:  # pragma: no cover - environment dependent
        raise SystemExit(
            "Could not load pipeline tables via Spark. Run inside the notebook "
            f"(Path A) or fix the table names. Original error: {exc}"
        )

    df_profiling_clustering = run_dtw_clustering(df_final, df_profiling)

    # Save back to the same table notebook 04 writes, so notebook 05 is unaffected.
    try:
        (
            spark.createDataFrame(df_profiling_clustering)  # noqa: F821
            .write.mode("overwrite")
            .saveAsTable(f"{LAKEHOUSE_NAME}.{OUTPUT_TABLE}")
        )
        print(f"✅ Saved DTW clusters to {LAKEHOUSE_NAME}.{OUTPUT_TABLE}")
    except Exception as exc:  # pragma: no cover
        print(f"❌ Could not save to Lakehouse ({exc}); returning DataFrame only.")
