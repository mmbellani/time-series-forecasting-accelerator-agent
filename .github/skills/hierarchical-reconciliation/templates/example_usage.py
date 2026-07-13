"""End-to-end example: reconcile base forecasts up a hierarchy and diagnose roll-up.

Run this AFTER notebook 06 has produced the `<scenario>_forecasts` table (with `y` and one
or more `y_hat_*` columns) and AFTER the `forecast-explainability` and `error-analysis`
skills have been used at the base-series level.

STEP 0 is mandatory: ask the data scientist which columns are the hierarchical levels
(top → bottom) and at which level to aggregate, then confirm with `describe_hierarchy`.

Two paths are shown:
  A) Inside a Fabric/Databricks notebook, reusing the in-memory forecast DataFrame.
  B) Standalone, loading the forecasts table from the Lakehouse via Spark.

Adjust SCENARIO, LEVELS, TARGET_LEVEL, table names, and column names to your run.
"""

# --- make the skill importable when running as a script ---------------------
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))  # skills/hierarchical-reconciliation

import pandas as pd

from reconcile import (
    describe_hierarchy,
    validate_hierarchy,
    aggregate_to_level,
    bottom_up,
    level_contributions,
    error_by_level,
    error_contribution,
    error_cancellation,
    plot_hierarchy_tree,
    plot_aggregate_actual_vs_forecast,
    plot_level_contributions,
    plot_contribution_bars,
    plot_waterfall,
    plot_error_by_level,
    plot_error_propagation,
    reconciliation_grid,
    narrate_hierarchy,
    narrate_reconciliation,
    narrate_error_propagation,
)

# ---------------------------------------------------------------------------
# Configuration — edit for your scenario (Step 0: confirm with the user!)
# ---------------------------------------------------------------------------
SCENARIO = "revenue_pnl"
DATE_VAR = "ds"
TARGET = "y"
UNIT = "USD"

# Hierarchy: top (coarsest) → bottom (finest). The finest is usually the base series.
LEVELS = ["region", "segment", "unique_id"]
TARGET_LEVEL = "region"     # where to aggregate/reconcile (or "Total")


# ===========================================================================
# PATH A — inside the notebook (objects already in memory)
# ===========================================================================
# `forecasts_df` : base actuals joined to predictions, carrying the LEVELS columns
#                  plus `y` and `y_hat_*`.
# `best_model_name` : optional, e.g. "y_hat_identity" (from notebook 06 selection).

def run_in_notebook(forecasts_df, levels=LEVELS, target_level=TARGET_LEVEL,
                    best_model_name=None, save_dir=None):
    # 0) Choose the prediction column to analyze
    if best_model_name is None:
        candidates = [c for c in forecasts_df.columns if c.startswith("y_hat_")]
        if not candidates:
            raise ValueError("No `y_hat_*` prediction columns found in forecasts_df.")
        best_model_name = candidates[0]
    y_pred = best_model_name

    # STEP 0 — confirm the hierarchy with the data scientist
    print("=== Hierarchy summary (confirm with the user) ===")
    print(describe_hierarchy(forecasts_df, levels).to_string(index=False))
    print("\n=== Nesting validation ===")
    print(validate_hierarchy(forecasts_df, levels))
    print("\n=== Narrative ===")
    print(narrate_hierarchy(forecasts_df, levels, target_level))

    fig, _ = plot_hierarchy_tree(forecasts_df, levels)
    _save(fig, save_dir, f"{SCENARIO}_hierarchy_tree.png")

    # 1) Composition — how base forecasts build the aggregate
    print(f"\n=== Aggregate composition at '{target_level}' ===")
    contrib = level_contributions(forecasts_df, levels, target_level,
                                  date_col=DATE_VAR, y_true=TARGET, y_pred=y_pred)
    print(contrib.head(10).to_string(index=False))

    fig, _ = plot_aggregate_actual_vs_forecast(forecasts_df, levels, target_level,
                                               date_col=DATE_VAR, y_true=TARGET, y_pred=y_pred)
    _save(fig, save_dir, f"{SCENARIO}_agg_fit_{target_level}.png")

    fig, _ = plot_contribution_bars(forecasts_df, levels, target_level,
                                    date_col=DATE_VAR, y_true=TARGET, y_pred=y_pred)
    _save(fig, save_dir, f"{SCENARIO}_contrib_bars_{target_level}.png")

    fig, _ = plot_level_contributions(forecasts_df, levels, target_level,
                                      date_col=DATE_VAR, y_true=TARGET, y_pred=y_pred)
    _save(fig, save_dir, f"{SCENARIO}_contrib_area_{target_level}.png")

    last_period = forecasts_df[DATE_VAR].max()
    fig, _ = plot_waterfall(forecasts_df, levels, target_level, period=last_period,
                            date_col=DATE_VAR, y_true=TARGET, y_pred=y_pred)
    _save(fig, save_dir, f"{SCENARIO}_waterfall_{target_level}.png")

    fig, _ = reconciliation_grid(forecasts_df, levels, date_col=DATE_VAR,
                                 y_true=TARGET, y_pred=y_pred)
    _save(fig, save_dir, f"{SCENARIO}_recon_grid.png")

    print("\n=== Composition narrative ===")
    print(narrate_reconciliation(forecasts_df, levels, target_level,
                                 date_col=DATE_VAR, y_true=TARGET, y_pred=y_pred, unit=UNIT))

    # 2) Error propagation — where errors are and how they roll up
    print("\n=== Error by level (propagation curve) ===")
    print(error_by_level(forecasts_df, levels, date_col=DATE_VAR,
                         y_true=TARGET, y_pred=y_pred).to_string(index=False))

    print("\n=== Error cancellation on aggregation ===")
    print(error_cancellation(forecasts_df, levels, date_col=DATE_VAR,
                             y_true=TARGET, y_pred=y_pred).to_string(index=False))

    print(f"\n=== Nodes driving aggregate error at '{target_level}' ===")
    print(error_contribution(forecasts_df, levels, target_level, date_col=DATE_VAR,
                             y_true=TARGET, y_pred=y_pred, top_n=10).to_string(index=False))

    fig, _ = plot_error_by_level(forecasts_df, levels, date_col=DATE_VAR,
                                 y_true=TARGET, y_pred=y_pred)
    _save(fig, save_dir, f"{SCENARIO}_error_by_level.png")

    fig, _ = plot_error_propagation(forecasts_df, levels, target_level, date_col=DATE_VAR,
                                    y_true=TARGET, y_pred=y_pred)
    _save(fig, save_dir, f"{SCENARIO}_error_propagation_{target_level}.png")

    print("\n=== Error-propagation narrative ===")
    print(narrate_error_propagation(forecasts_df, levels, target_level, date_col=DATE_VAR,
                                    y_true=TARGET, y_pred=y_pred, unit=UNIT))

    return aggregate_to_level(forecasts_df, levels, target_level,
                              date_col=DATE_VAR, y_true=TARGET, y_pred=y_pred)


# ===========================================================================
# PATH B — standalone, load forecasts from the Lakehouse
# ===========================================================================

def run_standalone(spark, levels=LEVELS, target_level=TARGET_LEVEL, save_dir=None):
    forecasts_df = spark.table(f"{SCENARIO}_forecasts").toPandas()
    candidates = [c for c in forecasts_df.columns if c.startswith("y_hat_")]
    y_pred = candidates[0] if candidates else "y_hat"

    print(describe_hierarchy(forecasts_df, levels).to_string(index=False))
    print(narrate_reconciliation(forecasts_df, levels, target_level,
                                 date_col=DATE_VAR, y_true=TARGET, y_pred=y_pred, unit=UNIT))
    print(narrate_error_propagation(forecasts_df, levels, target_level,
                                    date_col=DATE_VAR, y_true=TARGET, y_pred=y_pred, unit=UNIT))

    fig, _ = reconciliation_grid(forecasts_df, levels, date_col=DATE_VAR,
                                 y_true=TARGET, y_pred=y_pred)
    _save(fig, save_dir, f"{SCENARIO}_recon_grid.png")
    return forecasts_df


def _save(fig, save_dir, name):
    if save_dir:
        out = Path(save_dir) / name
        fig.savefig(out, dpi=120, bbox_inches="tight")
        print(f"Saved {out}")


if __name__ == "__main__":
    # Tiny self-contained demo so the file runs without the pipeline.
    import numpy as np

    rng = np.random.default_rng(0)
    dates = pd.date_range("2023-01-01", periods=52, freq="W")

    # 3 regions × 2 segments × 2 series = 12 base series with a small hierarchy.
    rows = []
    for region in ["EMEA", "AMS", "APAC"]:
        base_level = {"EMEA": 300, "AMS": 500, "APAC": 200}[region]
        for segment in ["Enterprise", "SMB"]:
            for k in range(2):
                uid = f"{region}_{segment}_{k}"
                level = base_level * (1.0 + 0.3 * k) + rng.normal(0, 10)
                y = level + 40 * np.sin(np.arange(52) / 8.0) + rng.normal(0, 15, 52)
                # Forecast: slight under-forecast bias in EMEA (propagates), noise elsewhere.
                yhat = y - (rng.normal(8, 4, 52) if region == "EMEA" else rng.normal(0, 12, 52))
                for d, yy, yh in zip(dates, y, yhat):
                    rows.append({"unique_id": uid, "region": region, "segment": segment,
                                 "ds": d, "y": yy, "y_hat_demo": yh})
    demo = pd.DataFrame(rows)

    run_in_notebook(demo, levels=["region", "segment", "unique_id"],
                    target_level="region", best_model_name="y_hat_demo")
