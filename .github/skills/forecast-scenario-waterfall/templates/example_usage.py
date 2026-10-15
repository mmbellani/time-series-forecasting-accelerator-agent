"""Example: exact SHAP waterfall of the served blend + a business surge scenario for one product family.

Retrains the two blend quantiles of one cluster on all data (fast) and explains its served, not-yet-booked rows.
Run AFTER notebooks 08 and 09.
"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve()
sys.path.append(str(HERE.parents[1]))
sys.path.append(str(HERE.parents[2] / "forecasting-lightgbm-quantile"))
from forecast_scenario_waterfall import DEFAULT_GROUPS, blend_contributions, rollup_drivers, waterfall_steps  # noqa: E402
from forecasting_lightgbm_quantile import QuantileBlendEngine, make_folds  # noqa: E402

SCENARIO, CLUSTER, FAMILY = "durable_goods_monthly", "smooth", "HVAC Units"
DATA = HERE.parents[4] / "data" / SCENARIO
panel = pd.read_parquet(DATA / f"{SCENARIO}_clustered.parquet")
cfg = json.loads(pd.read_parquet(DATA / f"{SCENARIO}_quantile_config.parquet")["json"].iloc[0])
blend = cfg["committed"][CLUSTER]["blend"]

eng = QuantileBlendEngine(panel, fy_start_month=int(cfg.get("fy_start_month", 10)), tune_clusters=[CLUSTER], qgrid=[blend["q_lo"], blend["q_hi"]])
served_months = [f for f in make_folds(eng.data_max, 1, eng.fy_start_month) if f["future"]][0]["months"]
models = eng.train(eng.data_max)
rows = eng.build_frame(eng.data_max, served_months, models, mode="strict")
rows["family"] = rows["unique_id"].map(panel.groupby("unique_id")["product_family"].first())
rows["blend"] = blend["w"] * rows[f"q{int(blend['q_lo'] * 100)}"] + (1 - blend["w"]) * rows[f"q{int(blend['q_hi'] * 100)}"]

contrib = blend_contributions(models[CLUSTER], blend, rows, eng.model_features)
drivers = rollup_drivers(contrib, by=rows["family"], baseline_features=eng.cats).set_index("group")
print(drivers.round(0).to_string())

row = drivers.loc[FAMILY].to_dict()
unbooked = float(rows.loc[rows["family"] == FAMILY, "blend"].sum())          # this cluster's served months for the family
booked = float(panel[(panel["product_family"] == FAMILY) & (panel["ds"] == eng.data_max) & (panel["profile_cluster"] == CLUSTER)]["y"].sum())
steps = waterfall_steps(row, list(DEFAULT_GROUPS), unbooked, booked, "served quarter",
                        scenario={"name": "surge", "price_surge": 0.15, "qty_surge": 0.05})
print("\n" + steps[["step_order", "step", "measure", "value", "running_total", "is_what_if"]].round(0).to_string(index=False))
assert abs(steps.iloc[-1]["running_total"] - (unbooked * 1.15 * 1.05 + booked)) < 1e-6
