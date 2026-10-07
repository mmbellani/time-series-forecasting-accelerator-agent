"""Example: two gate cycles on the advanced-track forecast table (bootstrap, then a refit against the champion).

Scores a config by re-blending the stored quantile columns of ``<scenario>_quantile_forecasts`` (validation folds),
so no retraining is needed. Run AFTER notebook 09.
"""
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve()
sys.path.append(str(HERE.parents[1]))
sys.path.append(str(HERE.parents[2] / "forecasting-lightgbm-quantile"))
from drift_gate_champion_challenger import ParquetStore, Registry, model_card, run_cycle, wmape  # noqa: E402
from forecasting_lightgbm_quantile import committed_forecast  # noqa: E402

SCENARIO = "durable_goods_monthly"
DATA = HERE.parents[4] / "data" / SCENARIO
fc = pd.read_parquet(DATA / f"{SCENARIO}_quantile_forecasts.parquet")
val = fc[(fc["fold"] != "final") & fc["has_actual"]].copy()
committed = json.loads(pd.read_parquet(DATA / f"{SCENARIO}_quantile_config.parquet")["json"].iloc[0])["committed"]


def score_fn(config):
    scored = committed_forecast(val, config)
    per_fold = [wmape(g["y"], g["yhat_committed"]) for _, g in scored.groupby("fold")]
    return wmape(scored["y"], scored["yhat_committed"]), per_fold, scored["y"].to_numpy(), scored["yhat_committed"].to_numpy()


def toy_tuner():
    # a deliberately different recipe: median-heavy blends, no rules
    return {c: {"method": "blend", "blend": {"q_lo": 0.5, "q_hi": 0.8, "w": 0.6}, "rules": None} for c in committed}


store = ParquetStore(Path(tempfile.mkdtemp()) / "mlops")
reg = Registry(store, model_name=f"{SCENARIO}.quantile_blend", run_stamp="cycle_1")
s1 = run_cycle(reg, committed, score_fn)                    # no champion -> bootstrap
print("cycle 1:", {k: s1[k] for k in ("refit_wmape", "promote", "role", "version")})

reg2 = Registry(store, model_name=f"{SCENARIO}.quantile_blend", run_stamp="cycle_2")
s2 = run_cycle(reg2, committed, score_fn, tune_fn=toy_tuner, force_tuning=True)   # champion exists; forced tune -> challenger gate
print("cycle 2:", {k: s2[k] for k in ("refit_wmape", "champion_wmape_now", "promote", "role", "tuned", "alert")})
print(reg2.decisions()[["run_stamp", "gate", "verdict", "candidate_wmape", "champion_wmape", "threshold"]].round(2).to_string(index=False))
print("\n" + model_card(s2, committed, title="Quantile blend - model card"))
