"""Scaled accuracy metrics for panel forecasts: one yardstick across clusters.

WMAPE answers "how many currency units off?" (pooled, dollars never cancel).
Bias answers "net over or under?" (a WMAPE-optimal blend of a lumpy cluster is often
30-40 % LOW; without the bias column that is invisible).
MASE answers "did the model beat the dumbest forecast for THIS series?" - the per-series
MAE divided by that series' mean |one-step change| over its *training* history, so a
timing miss on a volatile series is not double-punished. Reported as the MEDIAN across
series (the typical series) and REVENUE-WEIGHTED (``wmase``, the big series). The plain
mean is unusable: a near-zero series posts a MASE in the thousands.

Also here: the ORACLE ceiling (best quantile per row - the floor no blend or rule can
beat) and the READABLE-vs-STRICT comparison (validation rows that carry the month's
actual drivers vs rows rebuilt exactly as served).

Public API
----------
- ``wmape``, ``bias_pct``, ``rmse``
- ``naive_scale``          : per-series MASE denominator from history <= origin
- ``scaled_metrics``       : WMAPE / bias / median MASE / wMASE / RMSSE for one forecast column
- ``metrics_by_group``     : the same per group x forecast column (long table)
- ``oracle_ceiling``       : WMAPE of the per-row best quantile
- ``readable_vs_strict``   : side-by-side table of the two validation modes
- ``narrate_metrics``      : plain-language summary
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# pooled metrics
# ---------------------------------------------------------------------------
def _pair(actual, pred):
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    m = ~np.isnan(a) & ~np.isnan(p)
    return a[m], p[m]


def wmape(actual, pred) -> float:
    """sum|a - p| / sum|a| * 100 - pooled, zero-safe, errors never cancel."""
    a, p = _pair(actual, pred)
    d = np.abs(a).sum()
    return np.nan if d == 0 else float(100.0 * np.abs(a - p).sum() / d)


def bias_pct(actual, pred) -> float:
    """sum(p - a) / sum|a| * 100 - positive = over-forecast."""
    a, p = _pair(actual, pred)
    d = np.abs(a).sum()
    return np.nan if d == 0 else float(100.0 * (p - a).sum() / d)


def rmse(actual, pred) -> float:
    a, p = _pair(actual, pred)
    return np.nan if len(a) == 0 else float(np.sqrt(np.mean((a - p) ** 2)))


# ---------------------------------------------------------------------------
# scaled (per-series) metrics
# ---------------------------------------------------------------------------
def naive_scale(panel: pd.DataFrame, origin, id_col="unique_id", date_col="ds", target="y") -> pd.DataFrame:
    """Per-series MASE / RMSSE denominators from history <= origin (leak-free).

    Returns a frame indexed by series with ``scale1`` = mean |y_t - y_{t-1}| and
    ``scale2`` = mean (y_t - y_{t-1})^2.
    """
    h = panel[(panel[date_col] <= origin) & panel[target].notna()].sort_values([id_col, date_col])
    d = h.groupby(id_col, observed=True)[target].diff()
    return pd.DataFrame({"scale1": d.abs().groupby(h[id_col], observed=True).mean(),
                         "scale2": (d ** 2).groupby(h[id_col], observed=True).mean()})


def scaled_metrics(frame: pd.DataFrame, pred_col: str, actual_col="y", id_col="unique_id",
                   scales: Optional[pd.DataFrame] = None) -> Dict[str, float]:
    """WMAPE, bias, RMSE and - when ``scales`` is given - median MASE, revenue-weighted MASE, RMSSE.

    ``scales`` is the output of :func:`naive_scale` (one row per series). When the frame
    spans several origins, pass the mean of the per-origin scales or call per fold.
    """
    s = frame[frame[actual_col].notna() & frame[pred_col].notna()]
    if s.empty:
        return {}
    y, p = s[actual_col].to_numpy(float), s[pred_col].to_numpy(float)
    e = p - y
    out = {"n_rows": int(len(s)), "wmape": wmape(y, p), "bias_pct": bias_pct(y, p), "rmse": float(np.sqrt(np.mean(e ** 2)))}
    if scales is None:
        return out
    sc1 = s[id_col].astype(str).map(scales["scale1"].rename(index=str)).to_numpy(float)
    sc2 = s[id_col].astype(str).map(scales["scale2"].rename(index=str)).to_numpy(float)
    per = (pd.DataFrame({id_col: s[id_col].astype(str).values,
                         "se": np.abs(e) / np.where(sc1 > 0, sc1, np.nan),
                         "sse": e ** 2 / np.where(sc2 > 0, sc2, np.nan),
                         "ay": np.abs(y)})
           .groupby(id_col).agg(mase=("se", "mean"), msse=("sse", "mean"), ay=("ay", "sum"))
           .replace([np.inf, -np.inf], np.nan).dropna())
    if per.empty:
        out.update(n_series=0, mase_med=np.nan, wmase=np.nan, rmsse=np.nan)
        return out
    w = per["ay"] / per["ay"].sum() if per["ay"].sum() > 0 else pd.Series(1.0 / len(per), index=per.index)
    out.update(n_series=int(len(per)), mase_med=float(per["mase"].median()), wmase=float((per["mase"] * w).sum()),
               rmsse=float(np.sqrt(per["msse"]).mean()))
    return out


def metrics_by_group(frame: pd.DataFrame, pred_cols: Sequence[str], group_cols: Sequence[str] = ("cluster",),
                     actual_col="y", id_col="unique_id", scales: Optional[pd.DataFrame] = None,
                     add_total: str = "ALL") -> pd.DataFrame:
    """Long table: one row per group x forecast column, plus an ``add_total`` row set over everything."""
    rows = []
    groups = list(frame.groupby(list(group_cols), observed=True)) if group_cols else []
    if add_total:
        groups.append((tuple([add_total] * max(1, len(group_cols))), frame))
    for key, g in groups:
        key = key if isinstance(key, tuple) else (key,)
        for col in pred_cols:
            m = scaled_metrics(g, col, actual_col, id_col, scales)
            if m:
                rows.append({**dict(zip(group_cols or ["group"], key)), "forecast": col, **m})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------
def oracle_ceiling(frame: pd.DataFrame, quantile_cols: Sequence[str], actual_col="y") -> Dict[str, float]:
    """WMAPE of the per-row best quantile - the floor that no blend or rule layer can beat."""
    s = frame[frame[actual_col].notna()]
    if s.empty:
        return {}
    P = s[list(quantile_cols)].to_numpy(float)
    A = s[actual_col].to_numpy(float)
    best_idx = np.argmin(np.abs(P - A[:, None]), axis=1)
    best = P[np.arange(len(s)), best_idx]
    share = pd.Series(np.array(quantile_cols)[best_idx]).value_counts(normalize=True).round(3).to_dict()
    return {"oracle_wmape": wmape(A, best), "best_quantile_share": share}


def readable_vs_strict(readable: pd.DataFrame, strict: pd.DataFrame, pred_cols: Sequence[str], group_col="cluster",
                       actual_col="y") -> pd.DataFrame:
    """Side-by-side WMAPE of the two validation modes per group and forecast column.

    A forecast whose readable score is much better than its strict score is grading itself
    with the answer key (contemporaneous drivers, realised lags); quote the strict number.
    """
    rows = []
    for g in sorted(set(readable[group_col].astype(str)) | set(strict[group_col].astype(str))):
        r, s = readable[readable[group_col].astype(str) == g], strict[strict[group_col].astype(str) == g]
        for col in pred_cols:
            rw, sw = wmape(r[actual_col], r[col]) if col in r else np.nan, wmape(s[actual_col], s[col]) if col in s else np.nan
            rows.append({group_col: g, "forecast": col, "readable_wmape": rw, "strict_wmape": sw, "gap_pts": sw - rw})
    return pd.DataFrame(rows)


def narrate_metrics(table: pd.DataFrame, group_col="cluster", forecast="committed", baseline="snaive") -> str:
    """One paragraph per group: WMAPE, bias, skill vs naive, median MASE."""
    lines = []
    for g, t in table.groupby(group_col):
        f = t[t["forecast"] == forecast]
        b = t[t["forecast"] == baseline]
        if f.empty:
            continue
        f = f.iloc[0]
        txt = f"{g}: {forecast} WMAPE {f['wmape']:.1f}% with net bias {f['bias_pct']:+.1f}%"
        if not b.empty:
            txt += f" vs seasonal naive {b.iloc[0]['wmape']:.1f}% ({b.iloc[0]['wmape'] - f['wmape']:+.1f} pts better)" if b.iloc[0]['wmape'] >= f['wmape'] \
                else f" vs seasonal naive {b.iloc[0]['wmape']:.1f}% (naive is {f['wmape'] - b.iloc[0]['wmape']:.1f} pts BETTER - review)"
        if "mase_med" in f and pd.notna(f["mase_med"]):
            txt += f"; median MASE {f['mase_med']:.2f} ({'beats' if f['mase_med'] < 1 else 'does not beat'} one-step naive for the typical series)"
        if abs(f["bias_pct"]) > 15:
            txt += ". Bias exceeds 15% - the total is " + ("over" if f["bias_pct"] > 0 else "under") + "-forecast even if WMAPE looks acceptable."
        lines.append(txt)
    return "\n".join(lines)
