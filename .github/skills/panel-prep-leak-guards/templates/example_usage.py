"""Example: prepare the synthetic raw export (notebook 07) with the leak guards and print the leak check."""
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from panel_prep_leak_guards import prepare_panel  # noqa: E402

SCENARIO = "durable_goods_monthly"
DATA = Path(__file__).resolve().parents[4] / "data" / SCENARIO
raw = pd.read_parquet(DATA / f"{SCENARIO}_raw.parquet")

panel, report = prepare_panel(raw, id_col="unique_id", date_col="period_start_utc", target="net_revenue_usd", qty_col="units_shipped",
                              orders_col="order_count", extract_col="extract_id", ts_col="extract_ts", min_coverage=0.90)
print(f"extract used {report['extract_used']} of {report['n_extracts']} | rows {report['rows']:,} | series {report['series']} | "
      f"data through {report['data_max'].date()}")
print("trailing-edge coverage (last months):\n" + report["trailing_edge"]["coverage"].tail(4).to_string())
print("dropped months:", [m.strftime("%Y-%m") for m in report["trailing_edge"]["drop_months"]])
print("leak check  stacked:", {k: round(v, 3) for k, v in report["leak_check_stacked"].items()})
print("leak check  pinned :", {k: round(v, 3) for k, v in report["leak_check_pinned"].items()})
print(panel.head())
