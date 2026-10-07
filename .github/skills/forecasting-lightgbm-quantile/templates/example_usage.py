"""Example: per-cluster LightGBM quantile blend with an as-served commit gate (compact run).

Uses two validation folds and a reduced quantile grid so it finishes in about a minute on
the synthetic durable-goods panel. Run AFTER notebook 08 (``<scenario>_clustered``).
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from forecasting_lightgbm_quantile import (QuantileBlendEngine, commit_gate, committed_forecast, crossing_rate,  # noqa: E402
                                           make_folds, oracle_wmape, revenue_focus, tune_blend)

SCENARIO = "durable_goods_monthly"
DATA = Path(__file__).resolve().parents[4] / "data" / SCENARIO
panel = pd.read_parquet(DATA / f"{SCENARIO}_clustered.parquet")

QGRID = [0.2, 0.4, 0.5, 0.7, 0.8, 0.9]
eng = QuantileBlendEngine(panel, cluster_col="profile_cluster", tune_clusters=["strategic", "smooth", "erratic"],
                          cats=["product_group", "region", "channel"], fy_start_month=10, qgrid=QGRID)
folds = make_folds(eng.data_max, n_val=2, fy_start_month=10)
val = [f for f in folds if not f["future"]]

strict, readable = [], []
for f in val:
    models = eng.train(f["origin"])
    strict.append(eng.build_frame(f["origin"], f["months"], models, mode="strict"))
    readable.append(eng.build_frame(f["origin"], f["months"], models, mode="readable"))
    print(f"{f['name']} {f['quarter']}: crossing rate after rearrangement {crossing_rate(strict[-1], QGRID):.3f}")

focus = revenue_focus(panel, top_share=0.80)
committed, rows = {}, []
for clu in eng.tune_clusters:
    best = tune_blend(strict, clu, focus=focus, bias_cap=0.15, lo_grid=(0.2, 0.4, 0.5), hi_grid=(0.7, 0.8, 0.9))
    gate = commit_gate(strict, clu, best["blend"], focus=focus, readable_frames=readable)
    committed[clu] = {"method": gate["method"], "blend": best["blend"], "rules": gate["rules"]}
    rows.append({"cluster": clu, **best["blend"], "blend_strict": best["wmape"], "bias": best["bias"], "snaive": gate["snaive"],
                 "rules_readable": gate.get("rules_readable"), "rules_strict": gate["rules_strict"], "method": gate["method"],
                 "oracle": oracle_wmape(strict, clu, QGRID)})
print(pd.DataFrame(rows).round(1).to_string(index=False))

final = eng.train(eng.data_max)
served = committed_forecast(eng.build_frame(eng.data_max, folds[-1]["months"], final, mode="strict"), committed)
print(f"\nserved {folds[-1]['quarter']}: {served['unique_id'].nunique()} tuned series, "
      f"committed total {served['yhat_committed'].sum() / 1e6:.1f} M vs seasonal naive {served['snaive'].sum() / 1e6:.1f} M")
