"""Aggregate anchor + reconciliation (notebook 11 as a module).

Monthly bottom-up forecasts are accurate in flat quarters and systematically LOW in surge
quarters (trees cannot predict above their training range and the misses all point the
same way). A pooled LightGBM over the series x fiscal-quarter panel of a GROUP (product
family, region, ...) summed bottom-up is a better judge of the quarter total: its upper
quantile is right in surge quarters, its central estimate in flat ones, and the sum of
per-series MEDIANS under-forecasts a lumpy total (medians of right-skewed distributions
sit below their means; sums add means) -> anchor aggregates to q75 / the L2 mean, never q50.

The resolution is a RANGE: ``blend`` (bottom-up, no scaling) .. ``upside`` (blend scaled so
the group quarter total equals the anchor's upper quantile) with ``plateau`` (central
estimate) as a technical column. The same scaling is applied to the validation folds so the
range is scored before it is published.

Public API
----------
- ``FiscalQuarters``        : quarter index / label / months for a fiscal year start month
- ``quarterly_panel``       : series x quarter panel with quarterly lags, ratios, level
- ``fit_predict_outputs``   : raw + ratio LightGBM quantile/mean outputs + simple totals
- ``backtest_anchor``       : leak-free backtest of every output on the group total
- ``nowcast_anchor``        : served quarter = booked actual + full-quarter forecast x (1 - booked share)
- ``reconcile``             : scale the not-yet-booked bottom-up to the anchor (one factor per group x view)
- ``fold_views``            : blend / upside / plateau vs actual per validation fold
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    import lightgbm as lgb
except Exception:  # pragma: no cover
    lgb = None

DEFAULT_QUANTILES = (0.10, 0.25, 0.50, 0.70, 0.75, 0.90)
DEFAULT_PARAMS = {"objective": "quantile", "boosting_type": "gbdt", "random_state": 42, "n_jobs": -1, "verbose": -1,
                  "n_estimators": 300, "learning_rate": 0.03, "num_leaves": 6, "max_depth": 4, "min_child_samples": 15,
                  "reg_alpha": 1.0, "reg_lambda": 5.0, "subsample": 0.8, "subsample_freq": 1, "colsample_bytree": 0.8}
BASE_FEATS = ["lag1", "lag2", "lag3", "lag4", "ma4", "qoq", "yoy", "qty_lag1", "price_lag1", "fq"]


class FiscalQuarters:
    def __init__(self, fy_start_month: int = 10):
        self.fy_start_month = fy_start_month

    def parts(self, ts: pd.Timestamp):
        fm = ((ts.month - self.fy_start_month) % 12) + 1
        return ts.year + (1 if ts.month >= self.fy_start_month else 0), (fm - 1) // 3 + 1, fm

    def index(self, ts: pd.Timestamp) -> int:
        fy, fq, _ = self.parts(pd.Timestamp(ts))
        return fy * 4 + (fq - 1)

    def label(self, qi: int) -> str:
        return f"FY{(qi // 4) % 100:02d}-Q{qi % 4 + 1}"

    def months(self, qi: int) -> List[pd.Timestamp]:
        fy, fq = qi // 4, qi % 4 + 1
        m0 = (self.fy_start_month + 3 * (fq - 1) - 1) % 12 + 1
        y0 = fy - 1 if m0 >= self.fy_start_month else fy
        return [pd.Timestamp(year=y0, month=m0, day=1) + pd.DateOffset(months=i) for i in range(3)]


def complete_quarters(panel: pd.DataFrame, fq: FiscalQuarters, date_col="ds") -> List[int]:
    qi = panel[date_col].map(fq.index)
    n = panel.groupby(qi)[date_col].nunique()
    return sorted(n[n == 3].index)


def quarterly_panel(d: pd.DataFrame, fq: FiscalQuarters, complete: Sequence[int], cats: Sequence[str], id_col="unique_id",
                    date_col="ds", target="y", qty_col: Optional[str] = "quantity", extra_q: Optional[int] = None) -> pd.DataFrame:
    """Series x quarter panel (complete quarters + optional served quarter) with quarterly features and a floored level."""
    d = d.copy()
    d["qi"] = d[date_col].map(fq.index)
    agg = {"y": (target, "sum"), **{c: (c, "last") for c in cats}}
    if qty_col and qty_col in d:
        agg["qty"] = (qty_col, "sum")
    q = d.groupby([id_col, "qi"], observed=True).agg(**agg).reset_index()
    if "qty" not in q:
        q["qty"] = np.nan
    q = q[q["qi"].isin(complete)]
    quarters = sorted(set(q["qi"]) | ({extra_q} if extra_q is not None else set()))
    idx = pd.MultiIndex.from_product([q[id_col].unique(), quarters], names=[id_col, "qi"])
    q = q.set_index([id_col, "qi"]).reindex(idx).reset_index()
    hist = (q["qi"] != extra_q) if extra_q is not None else pd.Series(True, index=q.index)
    q.loc[hist, ["y", "qty"]] = q.loc[hist, ["y", "qty"]].fillna(0.0)
    for c in cats:
        q[c] = q.groupby(id_col)[c].transform(lambda s: s.ffill().bfill())
    q = q.sort_values([id_col, "qi"]).reset_index(drop=True)
    g = q.groupby(id_col)
    for k in (1, 2, 3, 4, 5):
        q[f"lag{k}"] = g["y"].shift(k)
    q["ma4"] = q[["lag1", "lag2", "lag3", "lag4"]].mean(axis=1)
    q["qoq"] = (q["lag1"] / q["lag2"].replace(0, np.nan)).clip(0.2, 5.0)
    q["yoy"] = (q["lag1"] / q["lag5"].replace(0, np.nan)).clip(0.2, 5.0)
    q["qty_lag1"] = g["qty"].shift(1)
    q["price_lag1"] = q["lag1"] / q["qty_lag1"].replace(0, np.nan)
    q["fq"] = q["qi"] % 4 + 1
    lvl = q[["lag1", "lag2", "lag3", "lag4"]].abs().mean(axis=1)
    floor = float(np.nanpercentile(lvl[lvl > 0], 5)) if (lvl > 0).any() else 1.0
    q["lvl"] = np.where(lvl.notna(), np.maximum(lvl, floor), np.nan)
    return q


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, cats: Sequence[str], target_kind="raw",
                quantiles: Sequence[float] = DEFAULT_QUANTILES, params: Optional[dict] = None) -> pd.DataFrame:
    """Quantile + L2-mean predictions per test row. 'ratio' fits y/lvl with mean-1 weights and scales back."""
    if lgb is None:
        raise ImportError("lightgbm is required")
    params = params or DEFAULT_PARAMS
    feats = BASE_FEATS + list(cats)
    tr = train.dropna(subset=["y"]).copy()
    if target_kind == "ratio":
        tr = tr[tr["lvl"] > 0]
        yt, w = (tr["y"] / tr["lvl"]).clip(-2.0, 6.0), tr["lvl"] / tr["lvl"].mean()
    else:
        yt, w = tr["y"], None
    test = test.copy()
    for c in cats:
        cat = pd.CategoricalDtype(sorted(set(train[c].dropna().astype(str)) | set(test[c].dropna().astype(str))))
        tr[c], test[c] = tr[c].astype(str).astype(cat), test[c].astype(str).astype(cat)
    X, Xt = tr[feats], test[feats]
    scale = test["lvl"].to_numpy(float) if target_kind == "ratio" else 1.0
    out = pd.DataFrame(index=test.index)
    for qq in quantiles:
        out[f"q{int(qq * 100)}"] = lgb.LGBMRegressor(**{**params, "alpha": qq}).fit(X, yt, sample_weight=w, categorical_feature=list(cats)).predict(Xt) * scale
    out["mean"] = lgb.LGBMRegressor(**{**params, "objective": "l2"}).fit(X, yt, sample_weight=w, categorical_feature=list(cats)).predict(Xt) * scale
    if target_kind == "ratio":
        miss = ~np.isfinite(scale)
        for c in out.columns:
            out.loc[miss, c] = test.loc[miss, "lag1"].to_numpy()
    return out


def fit_predict_outputs(q: pd.DataFrame, train: pd.DataFrame, test: pd.DataFrame, tq: int, cats: Sequence[str],
                        quantiles: Sequence[float] = DEFAULT_QUANTILES, params: Optional[dict] = None) -> Tuple[Dict[str, float], Dict[str, tuple]]:
    """Every candidate for the quarter total: simple totals + raw / ratio model outputs summed bottom-up."""
    tot = q[q["qi"] < tq].groupby("qi")["y"].sum()
    fcs = {"TOTAL last quarter": tot.get(tq - 1, np.nan), "TOTAL snaive": tot.get(tq - 4, np.nan),
           "TOTAL yoy-growth naive": (tot.get(tq - 4, np.nan) * tot.get(tq - 1, np.nan) / tot.get(tq - 5, np.nan)
                                      if (tq - 5) in tot.index and tot.get(tq - 5, 0) > 0 else np.nan)}
    band = {}
    for kind in ("raw", "ratio"):
        p = fit_predict(train, test, cats, kind, quantiles, params)
        for c in p.columns:
            if c in ("q10", "q25"):
                continue
            fcs[f"Q-LGBM {kind} {c}"] = float(p[c].sum())
        band[kind] = (float(p["q10"].sum()), float(p["q90"].sum())) if "q10" in p and "q90" in p else (np.nan, np.nan)
    return fcs, band


def backtest_anchor(panel: pd.DataFrame, fq: FiscalQuarters, groups: Iterable[str], group_col: str, cats: Sequence[str], n_folds=5,
                    id_col="unique_id", date_col="ds", target="y", qty_col="quantity", quantiles=DEFAULT_QUANTILES,
                    params: Optional[dict] = None, min_train_rows=30) -> pd.DataFrame:
    """Long table: group x quarter x method -> actual, forecast, signed error %, APE % (leak-free, last n_folds complete quarters)."""
    complete = complete_quarters(panel, fq, date_col)
    rows = []
    for g in groups:
        d = panel[panel[group_col] == g]
        q = quarterly_panel(d, fq, complete, cats, id_col, date_col, target, qty_col)
        for tq in complete[-n_folds:]:
            train, test = q[(q["qi"] < tq) & q["lag1"].notna()], q[q["qi"] == tq]
            if len(train) < min_train_rows or test.empty:
                continue
            actual = float(test["y"].sum())
            fcs, _ = fit_predict_outputs(q, train, test, tq, cats, quantiles, params)
            for k, v in fcs.items():
                if v is not None and np.isfinite(v) and actual:
                    rows.append({"group": g, "quarter": fq.label(tq), "qi": tq, "method": k, "actual": actual, "forecast": v,
                                 "error_pct": (v - actual) / abs(actual) * 100.0, "ape_pct": abs(v - actual) / abs(actual) * 100.0})
    return pd.DataFrame(rows)


def summarize_backtest(backtest: pd.DataFrame) -> pd.DataFrame:
    return (backtest.groupby(["group", "method"]).agg(mean_ape=("ape_pct", "mean"), max_ape=("ape_pct", "max"), mean_signed=("error_pct", "mean"),
                                                      within_10=("ape_pct", lambda s: int((s <= 10).sum()))).reset_index())


def nowcast_anchor(panel: pd.DataFrame, fq: FiscalQuarters, group: str, group_col: str, cats: Sequence[str], served_q: int, data_max,
                   views: Dict[str, str], summary: pd.DataFrame, id_col="unique_id", date_col="ds", target="y", qty_col="quantity",
                   quantiles=DEFAULT_QUANTILES, params: Optional[dict] = None) -> dict:
    """Served quarter anchor per view: booked actual + full-quarter forecast x (1 - typical booked share)."""
    complete = complete_quarters(panel, fq, date_col)
    d = panel[panel[group_col] == group]
    qs = quarterly_panel(d, fq, complete, cats, id_col, date_col, target, qty_col, extra_q=served_q)
    train, test = qs[(qs["qi"] < served_q) & qs["lag1"].notna()], qs[qs["qi"] == served_q]
    months = fq.months(served_q)
    known = [m for m in months if m <= pd.Timestamp(data_max)]
    pos = [months.index(m) for m in known]
    known_actual = float(d[d[date_col].isin(known)][target].sum())
    shares = []
    for qi in complete[-4:]:
        mm = fq.months(qi)
        tot = d[d[date_col].isin(mm)][target].sum()
        if tot > 0 and pos:
            shares.append(d[d[date_col].isin([mm[i] for i in pos])][target].sum() / tot)
    share_known = float(np.mean(shares)) if shares else 0.0
    fcs, band = fit_predict_outputs(qs, train, test, served_q, cats, quantiles, params)
    served_total = {k: known_actual + v * (1.0 - share_known) for k, v in fcs.items() if v is not None and np.isfinite(v)}
    gsum = summary[summary["group"] == group].set_index("method")
    best = gsum["mean_ape"].idxmin() if len(gsum) else None
    out_views = {}
    for view, want in views.items():
        m = best if want == "backtest" or want not in served_total else want
        out_views[view] = {"method": m, "full_quarter": fcs[m], "served_total": served_total[m],
                           "backtest_mean_ape": float(gsum.loc[m, "mean_ape"]) if m in gsum.index else np.nan}
    return {"group": group, "quarter": fq.label(served_q), "known_months": [m.strftime("%Y-%m") for m in known], "known_actual": known_actual,
            "share_known": share_known, "views": out_views, "backtest_best": best, "all_outputs": served_total,
            "band_q10_q90": tuple(known_actual + b * (1 - share_known) for b in band["raw"])}


def reconcile(served: pd.DataFrame, anchors: Dict[str, dict], group_col="group", future_col="is_future", blend_col="forecast_blend") -> pd.DataFrame:
    """Scale the not-yet-booked rows of each group so the group total equals each view's anchor; booked rows keep actuals."""
    out = served.copy()
    for view in next(iter(anchors.values()))["views"]:
        out[f"forecast_{view}"] = out[blend_col]
        out[f"{view}_factor"], out[f"{view}_anchor"] = 1.0, ""
    for g, a in anchors.items():
        m = (out[group_col] == g).to_numpy()
        fut = m & out[future_col].to_numpy(bool)
        known_sum = float(out.loc[m & ~out[future_col].to_numpy(bool), blend_col].sum())
        bottom = float(out.loc[fut, blend_col].sum())
        for view, v in a["views"].items():
            target = v["served_total"] - known_sum
            if bottom <= 0 or not np.isfinite(target) or target <= 0:
                continue
            k = target / bottom
            out.loc[fut, f"forecast_{view}"] = out.loc[fut, blend_col] * k
            out.loc[m, f"{view}_factor"] = k
            out.loc[m, f"{view}_anchor"] = f"{v['method']} @ {a['quarter']}"
    return out


def fold_views(bottom_up: pd.DataFrame, backtest: pd.DataFrame, views: Dict[str, dict]) -> pd.DataFrame:
    """bottom_up rows {group, quarter, actual, blend} + backtest -> blend / upside / plateau totals, factors and APEs per fold.

    ``views`` = {view: {group: method}} or {view: method} (same output for every group).
    """
    rows = []
    for r in bottom_up.itertuples(index=False):
        row = {"group": r.group, "quarter": r.quarter, "actual": r.actual, "blend": r.blend,
               "blend_ape": abs(r.blend - r.actual) / abs(r.actual) * 100 if r.actual else np.nan}
        for view, spec in views.items():
            method = spec.get(r.group) if isinstance(spec, dict) else spec
            bt = backtest[(backtest["group"] == r.group) & (backtest["quarter"] == r.quarter) & (backtest["method"] == method)]
            anchor = float(bt["forecast"].iloc[0]) if len(bt) else np.nan
            k = anchor / r.blend if np.isfinite(anchor) and r.blend > 0 else 1.0
            row[view], row[f"{view}_factor"] = r.blend * k, k
            row[f"{view}_ape"] = abs(r.blend * k - r.actual) / abs(r.actual) * 100 if r.actual else np.nan
        rows.append(row)
    return pd.DataFrame(rows)
