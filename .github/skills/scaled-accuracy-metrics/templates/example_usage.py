"""Example: one yardstick across clusters on the advanced-track forecast table.

Run AFTER notebook 09 (``<scenario>_quantile_forecasts``) and with the clustered panel
(``<scenario>_clustered``) available. Works on the local parquet fallback or on Spark tables.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from scaled_accuracy_metrics import metrics_by_group, naive_scale, narrate_metrics, oracle_ceiling  # noqa: E402

SCENARIO = "durable_goods_monthly"
ROOT = Path(__file__).resolve().parents[4]          # repo root
DATA = ROOT / "data" / SCENARIO

panel = pd.read_parquet(DATA / f"{SCENARIO}_clustered.parquet")
fc = pd.read_parquet(DATA / f"{SCENARIO}_quantile_forecasts.parquet")
panel["ds"], fc["ds"], fc["origin"] = pd.to_datetime(panel["ds"]), pd.to_datetime(fc["ds"]), pd.to_datetime(fc["origin"])

tables = []
for fold, f in fc[fc["fold"] != "final"].groupby("fold"):
    scales = naive_scale(panel, origin=f["origin"].iloc[0])
    t = metrics_by_group(f, pred_cols=["yhat_committed", "snaive"], group_cols=["profile_cluster"], scales=scales)
    t["fold"] = fold
    tables.append(t)
table = pd.concat(tables, ignore_index=True)
cols = ["fold", "profile_cluster", "forecast", "n_rows", "wmape", "bias_pct", "mase_med", "wmase"]
print(table[cols].round(2).to_string(index=False))

qcols = [c for c in fc.columns if c.startswith("q") and c[1:].isdigit()]
print("\noracle ceiling (all validation folds):", oracle_ceiling(fc[fc["fold"] != "final"], qcols)["oracle_wmape"])
print("\n" + narrate_metrics(table[table["fold"] == table["fold"].max()], group_col="profile_cluster", forecast="yhat_committed"))
