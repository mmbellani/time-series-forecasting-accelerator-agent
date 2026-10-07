"""Example: recency A/B per cluster with the surge gate (compact: 2 folds, blend quantiles only).

Run AFTER notebook 09 so ``<scenario>_quantile_config`` (the committed blends) exists.
"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve()
sys.path.append(str(HERE.parents[1]))
sys.path.append(str(HERE.parents[2] / "forecasting-lightgbm-quantile"))
from recency_weighting import ab_table, make_weight_fn, narrate, recommend, surge_flags  # noqa: E402
from forecasting_lightgbm_quantile import QuantileBlendEngine, apply_blend, bias_pct, make_folds, wmape  # noqa: E402

SCENARIO = "durable_goods_monthly"
DATA = HERE.parents[4] / "data" / SCENARIO
panel = pd.read_parquet(DATA / f"{SCENARIO}_clustered.parquet")
cfg = json.loads(pd.read_parquet(DATA / f"{SCENARIO}_quantile_config.parquet")["json"].iloc[0])
committed = cfg["committed"]
qgrid = sorted({q for c in committed.values() for q in (c["blend"]["q_lo"], c["blend"]["q_hi"])})

eng = QuantileBlendEngine(panel, fy_start_month=int(cfg.get("fy_start_month", 10)), qgrid=qgrid,
                          tune_clusters=[c for c in committed if c in set(panel["profile_cluster"].astype(str))])
folds = [f for f in make_folds(eng.data_max, 2, eng.fy_start_month) if not f["future"]]

results = []
for scheme in ["uniform", "hl9", "window18", "hl9_gated"]:
    frames = {clu: [] for clu in eng.tune_clusters}
    for f in folds:
        models = eng.train(f["origin"], weight_fn=make_weight_fn(scheme))
        fc = eng.build_frame(f["origin"], f["months"], models, "strict")
        for clu in eng.tune_clusters:
            frames[clu].append(apply_blend(fc[fc["profile_cluster"].astype(str) == clu], committed[clu]["blend"]))
    for clu, parts in frames.items():
        s = pd.concat(parts)
        s = s[s["has_actual"]]
        results.append({"cluster": clu, "scheme": scheme, "wmape": wmape(s["y"], s["yhat_blend"]), "bias_pct": bias_pct(s["y"], s["yhat_blend"])})
    print(f"  {scheme}: done")

ab = ab_table(results)
print(ab.pivot(index="scheme", columns="cluster", values="wmape").round(1))
print("\n" + narrate(recommend(ab)))
flags = surge_flags(eng.feat[eng.feat["ds"] <= eng.data_max], eng.data_max)
print(f"\nseries flagged as sustained step-up at {eng.data_max.date()}: {sum(flags.values())}")
