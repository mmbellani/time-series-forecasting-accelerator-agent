"""End-to-end example: moving-average forecasting + LightGBM benchmark.

Run this AFTER:
  * notebooks 03/04 have labelled each series with `profile_cluster`, and
  * notebook 06 has produced the `<scenario>_forecasts` table (with `y` and one or
    more `y_hat_*` LightGBM columns).

Every moving-average model is run twice — GLOBALLY over the entire panel and BY
`profile_cluster` — then benchmarked against the LightGBM baseline on the same
backtest windows.

Two paths are shown:
  A) Inside a Fabric/Databricks notebook, reusing in-memory DataFrames.
  B) Standalone, loading tables from the Lakehouse / catalog via Spark.

NOTE: `statsforecast` is required for the forecasting steps and is not yet in
`requirements.txt`. Install it first:  pip install "statsforecast>=1.7.0"

Adjust SCENARIO, table names, column names, FREQ, H, and SEASON to your run.
"""

# --- make the skill importable when running as a script ---------------------
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))  # skills/forecasting-moving-average

import pandas as pd

from forecasting_moving_average import (
    build_models,
    forecast_global,
    forecast_by_cluster,
    evaluate_forecasts,
    select_best,
    compare_to_baseline,
    narrate_comparison,
)

# ---------------------------------------------------------------------------
# Configuration — edit for your scenario
# ---------------------------------------------------------------------------
SCENARIO = "revenue_pnl"
UNIQUE_ID = "unique_id"
DATE_VAR = "ds"
TARGET = "y"
GROUP_COL = "profile_cluster"
UNIT = "units"

FREQ = "MS"        # monthly start; use "W", "D", etc. to match your granularity
H = 3              # forecast horizon per window
N_WINDOWS = 3      # rolling-origin backtest windows
SEASON = 12        # seasonal period (12 = monthly-yearly); used by seasonal window average


# ===========================================================================
# PATH A — inside the notebook (objects already in memory)
# ===========================================================================
# `panel_df`     : the modelling panel with UNIQUE_ID, DATE_VAR, TARGET, GROUP_COL.
# `forecasts_df` : the `<scenario>_forecasts` table with `y` and `y_hat_*` columns.

def run_in_notebook(panel_df, forecasts_df, save_dir=None):
    # 0) Build the window-average model set (SMA at 3/6/12 + seasonal variants)
    models = build_models(season_length=SEASON, add_naive_baselines=False)

    # 1) GLOBAL run — entire panel in one StatsForecast backtest
    print("=== Global moving-average backtest ===")
    cv_global = forecast_global(
        panel_df, h=H, freq=FREQ, models=models, n_windows=N_WINDOWS,
        id_col=UNIQUE_ID, date_col=DATE_VAR, target=TARGET,
    )
    print(evaluate_forecasts(cv_global, y_true=TARGET).to_string(index=False))

    # 2) BY profile_cluster — one backtest per cluster
    print("\n=== Per-cluster moving-average backtest ===")
    cv_cluster = forecast_by_cluster(
        panel_df, h=H, freq=FREQ, group_col=GROUP_COL, models=models,
        n_windows=N_WINDOWS, id_col=UNIQUE_ID, date_col=DATE_VAR, target=TARGET,
    )
    cluster_metrics = evaluate_forecasts(cv_cluster, y_true=TARGET, group_by=GROUP_COL)
    print(cluster_metrics.to_string(index=False))
    print("\nBest moving-average model per cluster:")
    print(select_best(cluster_metrics, metric="MAE", group_by=GROUP_COL).to_string(index=False))

    # 3) Benchmark GLOBAL vs the LightGBM baseline
    print("\n=== Global: MovingAverage vs LightGBM ===")
    res_global = compare_to_baseline(
        cv_global, forecasts_df, y_true=TARGET, id_col=UNIQUE_ID, date_col=DATE_VAR,
    )
    print(res_global["metrics"].to_string(index=False))
    print(narrate_comparison(res_global["metrics"], res_global["winner"], unit=UNIT))

    # 4) Benchmark PER-CLUSTER vs the LightGBM baseline
    print("\n=== Per-cluster: MovingAverage vs LightGBM ===")
    res_cluster = compare_to_baseline(
        cv_cluster, forecasts_df, y_true=TARGET, id_col=UNIQUE_ID,
        date_col=DATE_VAR, group_by=GROUP_COL,
    )
    print(res_cluster["metrics"].to_string(index=False))
    print(narrate_comparison(
        res_cluster["metrics"], res_cluster["winner"], unit=UNIT, group_by=GROUP_COL,
    ))

    # 5) Persist the comparison tables (optional)
    if save_dir:
        out = Path(save_dir)
        out.mkdir(parents=True, exist_ok=True)
        res_global["metrics"].to_csv(out / f"{SCENARIO}_moving_average_global.csv", index=False)
        res_cluster["metrics"].to_csv(out / f"{SCENARIO}_moving_average_by_cluster.csv", index=False)
        print(f"\nSaved comparison tables to {out}")

    return res_global, res_cluster


# ===========================================================================
# PATH B — standalone (load from Lakehouse / catalog)
# ===========================================================================

def run_standalone(spark, panel_table, forecasts_table, save_dir=None):
    panel_df = spark.table(panel_table).toPandas()
    forecasts_df = spark.table(forecasts_table).toPandas()
    return run_in_notebook(panel_df, forecasts_df, save_dir=save_dir)


if __name__ == "__main__":
    # Example: load CSVs exported from the pipeline and run the benchmark.
    panel_df = pd.read_csv(f"{SCENARIO}_panel.csv")
    forecasts_df = pd.read_csv(f"{SCENARIO}_forecasts.csv")
    run_in_notebook(panel_df, forecasts_df, save_dir=".")
