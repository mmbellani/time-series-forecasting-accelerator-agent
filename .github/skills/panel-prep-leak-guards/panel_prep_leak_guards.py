"""Panel preparation guards that prevent silently leaked backtests (notebook 07, section 8).

Each helper encodes a data problem that cost real time in the field:

* ``pin_latest_extract``      - several data extracts (pipeline runs) stacked in one table
                                repeat every series-month; lags computed on the stack see
                                the CURRENT month as "lag 2" and the backtest looks
                                unjustifiably good. Pick ONE extract before any feature.
* ``parse_utc_month``         - '2025-09-01T00:00:00Z' parses tz-aware; comparing it with a
                                naive timestamp raises or silently drops the last month.
* ``dedupe_series_month``     - revisions inside one extract: keep the last.
* ``fill_month_grid``         - absent months are zeros for quantity / orders / revenue;
                                the intermittent profile depends on them.
* ``guarded_price``           - revenue / 0 for credit notes and installation-only months
                                must be NaN, never inf.
* ``trailing_edge_coverage``  - late bookings thin the newest months; after gap filling
                                they look like a demand collapse. Measure coverage and
                                decide explicitly whether to drop them.
* ``lag_leak_check``          - the measurable symptom: on a stacked table the share of
                                rows where "lag k" equals the current value is far above
                                zero and corr(y, lag k) is inflated.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


def pin_latest_extract(raw: pd.DataFrame, extract_col="extract_id", ts_col: Optional[str] = "extract_ts",
                       pin: Optional[str] = None) -> Tuple[pd.DataFrame, str, int]:
    """Keep exactly one extract: ``pin`` if given and present, else the newest by ``ts_col`` (or the lexically last id)."""
    if extract_col not in raw.columns:
        return raw, "(single extract)", 1
    ids = raw[extract_col].dropna().unique()
    if pin is not None and pin in set(ids):
        chosen = pin
    elif ts_col and ts_col in raw.columns:
        chosen = raw.sort_values(ts_col)[extract_col].iloc[-1]
    else:
        chosen = sorted(ids)[-1]
    return raw[raw[extract_col] == chosen].copy(), str(chosen), int(len(ids))


def parse_utc_month(s: pd.Series) -> pd.Series:
    """Any date-like column (incl. '...Z' strings) -> naive month-start timestamps."""
    t = pd.to_datetime(s, utc=True, errors="coerce").dt.tz_localize(None)
    return t.dt.to_period("M").dt.to_timestamp()


def dedupe_series_month(df: pd.DataFrame, id_col="unique_id", date_col="ds") -> pd.DataFrame:
    return df.sort_values([id_col, date_col]).drop_duplicates([id_col, date_col], keep="last")


def fill_month_grid(df: pd.DataFrame, value_cols: Sequence[str], id_col="unique_id", date_col="ds", start=None, end=None,
                    fill_value=0.0) -> pd.DataFrame:
    """Full series x month grid; missing months get ``fill_value`` in ``value_cols``."""
    start = pd.Timestamp(start) if start is not None else df[date_col].min()
    end = pd.Timestamp(end) if end is not None else df[date_col].max()
    grid = pd.MultiIndex.from_product([df[id_col].unique(), pd.date_range(start, end, freq="MS")], names=[id_col, date_col]).to_frame(index=False)
    out = grid.merge(df[[id_col, date_col, *value_cols]], on=[id_col, date_col], how="left")
    out[list(value_cols)] = out[list(value_cols)].fillna(fill_value)
    return out


def guarded_price(revenue: pd.Series, quantity: pd.Series) -> pd.Series:
    q = quantity.astype(float)
    return pd.Series(np.where(q > 0, revenue.astype(float) / q.replace(0, np.nan), np.nan), index=revenue.index)


def trailing_edge_coverage(df: pd.DataFrame, id_col="unique_id", date_col="ds", activity_cols: Sequence[str] = ("quantity", "y"),
                           steady_window: Tuple[int, int] = (-15, -3), check_last: int = 3, min_coverage=0.90) -> Dict[str, object]:
    """Active series per month vs the median of a steady window; which trailing months fall below ``min_coverage``."""
    active = df[np.logical_or.reduce([df[c].fillna(0) != 0 for c in activity_cols if c in df])].groupby(date_col)[id_col].nunique()
    active = active.reindex(sorted(df[date_col].unique())).fillna(0)
    steady = active.iloc[steady_window[0]:steady_window[1]].median()
    coverage = (active / steady) if steady else active * np.nan
    drop = [m for m in coverage.index[-check_last:] if coverage.loc[m] < min_coverage]
    new_max = max(m for m in coverage.index if m not in drop) if len(coverage) > len(drop) else None
    return {"coverage": coverage.round(3), "steady_state_active": float(steady), "drop_months": drop, "data_max_after": new_max}


def lag_leak_check(frame: pd.DataFrame, id_col="unique_id", date_col="ds", target="y", lag=2) -> Dict[str, float]:
    """corr(y, lag k) and the share of rows where the 'lag' equals the current value - high values flag stacked extracts."""
    f = frame.sort_values([id_col, date_col]).copy()
    f["_lag"] = f.groupby(id_col)[target].shift(lag)
    m = f["_lag"].notna() & (f[target] != 0)
    if m.sum() < 3:
        return {"corr": np.nan, "share_identical": np.nan, "n": int(m.sum())}
    return {"corr": float(np.corrcoef(f.loc[m, target], f.loc[m, "_lag"])[0, 1]),
            "share_identical": float((f.loc[m, "_lag"] == f.loc[m, target]).mean()), "n": int(m.sum())}


def prepare_panel(raw: pd.DataFrame, id_col="unique_id", date_col="period_start_utc", target="net_revenue_usd", qty_col="units_shipped",
                  orders_col: Optional[str] = "order_count", extract_col="extract_id", ts_col="extract_ts", pin: Optional[str] = None,
                  start=None, min_coverage=0.90) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """The whole recipe in one call -> (prepared panel with unique_id/ds/y/quantity/orders/price_per_unit, report)."""
    one, chosen, n_extracts = pin_latest_extract(raw, extract_col, ts_col, pin)
    one = one.rename(columns={target: "y", qty_col: "quantity", **({orders_col: "orders"} if orders_col else {})}).copy()
    one["ds"] = parse_utc_month(one[date_col])
    one = dedupe_series_month(one, id_col, "ds")
    value_cols = ["y", "quantity"] + (["orders"] if orders_col else [])
    panel = fill_month_grid(one, value_cols, id_col, "ds", start=start)
    panel["price_per_unit"] = guarded_price(panel["y"], panel["quantity"])
    edge = trailing_edge_coverage(panel, id_col, "ds", ("quantity", "y"), min_coverage=min_coverage)
    if edge["drop_months"]:
        panel = panel[~panel["ds"].isin(edge["drop_months"])]
    stacked = raw.rename(columns={target: "y"}).copy()
    stacked["ds"] = parse_utc_month(stacked[date_col])
    report = {"extract_used": chosen, "n_extracts": n_extracts, "trailing_edge": edge,
              "leak_check_stacked": lag_leak_check(stacked[[id_col, "ds", "y"]], id_col, "ds", "y"),
              "leak_check_pinned": lag_leak_check(panel[[id_col, "ds", "y"]], id_col, "ds", "y"),
              "rows": int(len(panel)), "series": int(panel[id_col].nunique()), "data_max": panel["ds"].max()}
    return panel.sort_values([id_col, "ds"]).reset_index(drop=True), report
