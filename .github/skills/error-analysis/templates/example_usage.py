"""End-to-end example: evaluate forecast accuracy and decompose error by calendar.

Run this AFTER notebook 06 has produced the `<scenario>_forecasts` table (with `y` and
one or more `y_hat_*` columns) and AFTER the `forecast-explainability` skill has been used
to understand the model's drivers.

Two paths are shown:
  A) Inside a Fabric/Databricks notebook, reusing the in-memory forecast DataFrame.
  B) Standalone, loading the forecasts table from the Lakehouse via Spark.

Adjust SCENARIO, table names, and column names to your run.
"""

# --- make the skill importable when running as a script ---------------------
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))  # skills/error-analysis

import pandas as pd

from evaluate import (
    compute_errors,
    metric_summary,
    compare_models,
    metrics_by_calendar,
    error_boxplot,
    boxplot_grid,
    worst_buckets,
    narrate_errors,
)

# ---------------------------------------------------------------------------
# Configuration — edit for your scenario
# ---------------------------------------------------------------------------
SCENARIO = "revenue_pnl"
UNIQUE_ID = "unique_id"
DATE_VAR = "ds"
TARGET = "y"
UNIT = "USD"
CALENDAR_VARS = ["year", "quarter", "month", "week", "dayofweek"]


# ===========================================================================
# PATH A — inside the notebook (objects already in memory)
# ===========================================================================
# `forecasts_df` : actuals joined to predictions, with `y` and `y_hat_*` columns.
# `best_model_name` : optional, e.g. "y_hat_identity" (from notebook 06 selection).

def run_in_notebook(forecasts_df, best_model_name=None, save_dir=None):
    # 0) Choose the prediction column to analyze
    if best_model_name is None:
        candidates = [c for c in forecasts_df.columns if c.startswith("y_hat_")]
        if not candidates:
            raise ValueError("No `y_hat_*` prediction columns found in forecasts_df.")
        best_model_name = candidates[0]
    y_pred = best_model_name

    # 1) Per-row errors + calendar decomposition
    errors = compute_errors(
        forecasts_df, y_true=TARGET, y_pred=y_pred,
        date_col=DATE_VAR, id_col=UNIQUE_ID, calendar_vars=CALENDAR_VARS,
    )

    # 2) Overall accuracy
    print("=== Overall metrics ===")
    print(metric_summary(errors, y_true=TARGET, y_pred=y_pred).to_string())

    # 3) Compare model variants (all y_hat_* columns)
    print("\n=== Model comparison (sorted by MAE) ===")
    print(compare_models(forecasts_df, y_true=TARGET, sort_by="MAE").to_string(index=False))

    # 4) Decompose each metric by every calendar variable + box-plots
    for by in CALENDAR_VARS:
        print(f"\n=== Metrics by {by} ===")
        print(metrics_by_calendar(errors, by=by, y_pred=y_pred).to_string(index=False))

    # 5) Box-plots: one metric across all calendar variables (grid), plus per-metric
    for metric in ["MAE", "MAPE", "ME", "RMSE"]:
        fig, _ = boxplot_grid(errors, calendar_vars=CALENDAR_VARS, metric=metric)
        if save_dir:
            out = Path(save_dir) / f"{SCENARIO}_{metric.lower()}_grid.png"
            fig.savefig(out, dpi=120, bbox_inches="tight")
            print(f"Saved {out}")

    # Per-metric box-plot by month (the most common decomposition)
    for metric in ["MAE", "MAPE", "ME", "RMSE"]:
        fig, _ = error_boxplot(errors, by="month", metric=metric)
        if save_dir:
            out = Path(save_dir) / f"{SCENARIO}_{metric.lower()}_by_month.png"
            fig.savefig(out, dpi=120, bbox_inches="tight")
            print(f"Saved {out}")

    # 6) Worst buckets → hand-off to forecast-explainability
    print("\n=== Worst buckets (by MAE) ===")
    for by in CALENDAR_VARS:
        print(f"\n-- {by} --")
        print(worst_buckets(errors, by=by, metric="MAE", top_n=3).to_string(index=False))

    # 7) Narrative
    print("\n=== Narrative ===")
    print(narrate_errors(errors, calendar_vars=CALENDAR_VARS,
                         y_true=TARGET, y_pred=y_pred, unit=UNIT))

    return errors


# ===========================================================================
# PATH B — standalone, load forecasts from the Lakehouse
# ===========================================================================

def run_standalone(spark, save_dir=None):
    forecasts_df = spark.table(f"{SCENARIO}_forecasts").toPandas()
    candidates = [c for c in forecasts_df.columns if c.startswith("y_hat_")]
    y_pred = candidates[0] if candidates else "y_hat"

    errors = compute_errors(forecasts_df, y_true=TARGET, y_pred=y_pred,
                            date_col=DATE_VAR, id_col=UNIQUE_ID,
                            calendar_vars=CALENDAR_VARS)
    print(metric_summary(errors, y_true=TARGET, y_pred=y_pred).to_string())
    print(narrate_errors(errors, y_true=TARGET, y_pred=y_pred, unit=UNIT))

    fig, _ = boxplot_grid(errors, calendar_vars=CALENDAR_VARS, metric="MAE")
    if save_dir:
        fig.savefig(Path(save_dir) / f"{SCENARIO}_mae_grid.png", dpi=120, bbox_inches="tight")
    return errors


if __name__ == "__main__":
    # Tiny self-contained demo so the file runs without the pipeline.
    import numpy as np

    rng = np.random.default_rng(0)
    dates = pd.date_range("2023-01-01", periods=104, freq="W")
    demo = pd.DataFrame({
        UNIQUE_ID: "series_A",
        DATE_VAR: dates,
        TARGET: 100 + 20 * np.sin(np.arange(104) / 8.0) + rng.normal(0, 5, 104),
    })
    # A biased forecast that is worse in Q4 (months 10-12) to exercise decomposition.
    demo["y_hat_demo"] = demo[TARGET] - 3  # slight over-... actually under-forecast bias
    q4 = demo[DATE_VAR].dt.month.isin([10, 11, 12])
    demo.loc[q4, "y_hat_demo"] -= rng.normal(15, 8, q4.sum())

    run_in_notebook(demo, best_model_name="y_hat_demo")
