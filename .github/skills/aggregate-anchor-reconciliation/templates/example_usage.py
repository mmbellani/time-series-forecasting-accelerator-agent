"""Example: quarterly anchor backtest + the range blend .. upside on the served quarter (two families, 3 folds).

Run AFTER notebooks 08 and 09 (``<scenario>_clustered``, ``<scenario>_quantile_forecasts``).
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from aggregate_anchor_reconciliation import (FiscalQuarters, backtest_anchor, nowcast_anchor, reconcile,  # noqa: E402
                                             summarize_backtest)

SCENARIO = "durable_goods_monthly"
DATA = Path(__file__).resolve().parents[4] / "data" / SCENARIO
panel = pd.read_parquet(DATA / f"{SCENARIO}_clustered.parquet")
fc = pd.read_parquet(DATA / f"{SCENARIO}_quantile_forecasts.parquet")
panel["ds"], fc["ds"] = pd.to_datetime(panel["ds"]), pd.to_datetime(fc["ds"])

fq = FiscalQuarters(fy_start_month=10)
CATS = ["product_group", "region", "channel"]
groups = ["HVAC Units", "Pumps"]
bt = backtest_anchor(panel, fq, groups, group_col="product_family", cats=CATS, n_folds=3)
summary = summarize_backtest(bt)
print(summary.pivot(index="method", columns="group", values="mean_ape").round(1).sort_values(groups[0]))

views = {"upside": "Q-LGBM raw q75", "plateau": "Q-LGBM ratio mean"}
served = fc[fc["fold"] == "final"].copy()
served["group"] = served["unique_id"].map(panel.groupby("unique_id")["product_family"].first())
served = served[served["group"].isin(groups)]
served["forecast_blend"] = served["yhat_committed"]
served_q = fq.index(served["ds"].min())
anchors = {g: nowcast_anchor(panel, fq, g, "product_family", CATS, served_q, panel["ds"].max(), views, summary) for g in groups}
rec = reconcile(served, anchors, group_col="group", future_col="is_future")
tab = rec.groupby("group")[["forecast_blend", "forecast_upside", "forecast_plateau"]].sum() / 1e6
tab["upside_factor"] = rec.groupby("group")["upside_factor"].max()
print(f"\nserved {fq.label(served_q)} (M):\n" + tab.round(2).to_string())
