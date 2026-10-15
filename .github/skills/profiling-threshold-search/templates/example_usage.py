"""Example: objective SBC threshold search + business overlays on the advanced-track prepared panel."""
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from profiling_threshold_search import (business_overlays, candidate_backtests, classify, narrate_search,  # noqa: E402
                                        sbc_indicators, search_thresholds)

SCENARIO = "durable_goods_monthly"
DATA = Path(__file__).resolve().parents[4] / "data" / SCENARIO

panel = pd.read_parquet(DATA / f"{SCENARIO}_prepared.parquet")
panel["ds"] = pd.to_datetime(panel["ds"])

ind = sbc_indicators(panel, size_col="quantity", occurrence_col="orders")
bt = candidate_backtests(panel, target="y", horizon=6, season=12)
rev = panel.groupby("unique_id")["y"].sum()
results, best = search_thresholds(ind, bt, rev, n_iter=40, min_revenue_share=0.40, min_series=40)
print(narrate_search(results, best))

ind["profile"] = classify(ind, best["thres_cv2"], best["thres_adi"])
clusters = business_overlays(panel, ind.set_index("unique_id")["profile"], strategic_min_share=0.08)
print("\nprofile_cluster counts:\n" + clusters["profile_cluster"].value_counts().to_string())
