"""Objective Syntetos-Boylan threshold search + business overlays (notebook 08 as a module).

The textbook SBC cut-offs (ADI 1.32, CV^2 0.49) were derived for retail units. On revenue
panels with project deals and service contracts they are a guess. This module turns the
thresholds into a decision with an objective:

1. ``sbc_indicators``   - ADI (from occurrence months), CV^2 (of the winsorised non-zero
                          sizes) and SDDI, once per series.
2. ``candidate_backtests`` - a small set of simple methods, one per quadrant (seasonal
                          naive, 12-month median, Croston-style demand rates, last, zero),
                          backtested once per series on the last ``horizon`` periods.
3. ``search_thresholds`` - randomized search over (thres_cv2, thres_adi); each candidate
                          labels the series and ROUTES every series to its quadrant's
                          method; the objective is the pooled WMAPE of the whole portfolio
                          under that routing (so BOTH thresholds are identified), subject to
                          a GUARDRAIL: the regular group must keep a minimum revenue share.
4. ``business_overlays`` - strategic (one series above x % of revenue), possible_obsolete
                          (silent for the last N months), new_expansion (active only in the
                          last N months) -> ``profile_cluster``.

Column contract: ``unique_id``, ``ds``, a target (``y``), optionally a size column
(``quantity``) for CV^2 and an occurrence column (``orders``) for ADI.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

DEFAULT_METHOD_BY_PROFILE = {"smooth": "snaive", "erratic": "median12", "intermittent": "rate12", "lumpy": "rate24",
                             "constant": "last", "constant_zero": "zero"}
REGULAR = ("smooth", "erratic")


# ---------------------------------------------------------------------------
# indicators + classification
# ---------------------------------------------------------------------------
def _winsorize(x: np.ndarray, p: float) -> np.ndarray:
    if p <= 0 or x.size < 5:
        return x
    lo, hi = np.quantile(x, p), np.quantile(x, 1 - p)
    return np.clip(x, lo, hi)


def sbc_indicators(panel: pd.DataFrame, id_col="unique_id", date_col="ds", size_col="quantity",
                   occurrence_col: Optional[str] = "orders", winsor=0.05) -> pd.DataFrame:
    """One row per series: n_periods, n_demand, adi, cv2, sddi. Gap periods must already be zero rows."""
    rows = []
    for uid, g in panel.sort_values(date_col).groupby(id_col, sort=False):
        qty = g[size_col].fillna(0.0).to_numpy(float)
        occ = g[occurrence_col].fillna(0.0).to_numpy(float) if occurrence_col and occurrence_col in g else qty
        order_pos = np.flatnonzero(occ > 0) if (occ > 0).any() else np.flatnonzero(qty > 0)
        qty_pos = np.flatnonzero(qty > 0)
        n = int(qty.size)
        if order_pos.size == 0 or qty_pos.size == 0:
            rows.append({id_col: uid, "n_periods": n, "n_demand": int(qty_pos.size), "adi": np.inf, "cv2": np.nan, "sddi": np.nan})
            continue
        nz = _winsorize(qty[qty_pos], winsor)
        mean_nz = float(np.mean(nz))
        gaps = np.diff(order_pos)
        rows.append({id_col: uid, "n_periods": n, "n_demand": int(qty_pos.size), "adi": n / order_pos.size,
                     "cv2": float((np.std(nz) / mean_nz) ** 2) if mean_nz else np.nan,
                     "sddi": float(np.std(gaps)) if gaps.size else 0.0})
    return pd.DataFrame(rows)


def classify(ind: pd.DataFrame, thres_cv2: float, thres_adi: float, min_demand=3, cv2_const=0.0032) -> pd.Series:
    """SBC quadrant per series. A sparse series whose sizes are always identical has CV^2 = 0 but is NOT constant."""
    out = []
    for r in ind.itertuples(index=False):
        if r.n_demand <= min_demand or not np.isfinite(r.cv2):
            out.append("constant_zero")
            continue
        low_adi = r.adi < thres_adi
        if r.cv2 < cv2_const and low_adi:
            out.append("constant")
            continue
        out.append({(True, True): "smooth", (False, True): "intermittent", (True, False): "erratic",
                    (False, False): "lumpy"}[(low_adi, r.cv2 < thres_cv2)])
    return pd.Series(out, index=ind.index, name="profile")


# ---------------------------------------------------------------------------
# simple candidate methods, backtested once per series
# ---------------------------------------------------------------------------
def candidate_forecasts(train: np.ndarray, h: int, season=12) -> Dict[str, np.ndarray]:
    train = np.asarray(train, float)
    last = train[-1] if train.size else 0.0
    snaive = np.tile(train[-season:], int(math.ceil(h / season)))[:h] if train.size >= season else np.full(h, last)
    return {"snaive": snaive, "median12": np.full(h, float(np.median(train[-12:]))),
            "rate12": np.full(h, float(np.mean(train[-12:]))), "rate24": np.full(h, float(np.mean(train[-24:]))),
            "last": np.full(h, last), "zero": np.zeros(h)}


def candidate_backtests(panel: pd.DataFrame, id_col="unique_id", date_col="ds", target="y", horizon=6, season=12) -> Dict[str, dict]:
    """{series: {'act', 'n', 'scale', 'abs_err': {method: ...}, 'sq_err': {...}, 'mae': {...}}} - threshold independent."""
    bt = {}
    for uid, g in panel.sort_values(date_col).groupby(id_col, sort=False):
        arr = g[target].fillna(0.0).to_numpy(float)
        if arr.size <= max(horizon + 1, season + horizon):
            continue
        train, test = arr[:-horizon], arr[-horizon:]
        preds = candidate_forecasts(train, horizon, season)
        scale = np.mean(np.abs(train[season:] - train[:-season])) if train.size > season else np.nan
        rec = {"act": float(np.abs(test).sum()), "n": horizon, "scale": float(scale) if scale and scale > 0 else np.nan,
               "abs_err": {}, "sq_err": {}, "mae": {}}
        for k, p in preds.items():
            e = np.abs(test - p)
            rec["abs_err"][k], rec["sq_err"][k], rec["mae"][k] = float(e.sum()), float((e ** 2).sum()), float(e.mean())
        bt[uid] = rec
    return bt


def aggregate_metrics(bt: Dict[str, dict], routing: Dict[str, str]) -> Dict[str, float]:
    rows = [(bt[u], m) for u, m in routing.items() if u in bt]
    if not rows:
        return {"wmape": np.nan, "rmse": np.nan, "mase_med": np.nan, "n_series": 0}
    abs_err = sum(r["abs_err"][k] for r, k in rows)
    act, sq, n = sum(r["act"] for r, _ in rows), sum(r["sq_err"][k] for r, k in rows), sum(r["n"] for r, _ in rows)
    mases = [r["mae"][k] / r["scale"] for r, k in rows if r["scale"] == r["scale"]]
    return {"wmape": 100.0 * abs_err / act if act else np.nan, "rmse": math.sqrt(sq / n) if n else np.nan,
            "mase_med": float(np.median(mases)) if mases else np.nan, "n_series": len(rows)}


# ---------------------------------------------------------------------------
# the search
# ---------------------------------------------------------------------------
def search_thresholds(ind: pd.DataFrame, bt: Dict[str, dict], revenue_by_id: pd.Series, id_col="unique_id",
                      n_iter=60, cv2_range=(0.10, 1.20), adi_range=(1.05, 2.50), min_revenue_share=0.40, min_series=40,
                      method_by_profile: Optional[Dict[str, str]] = None, textbook=(0.49, 1.32), random_state=42,
                      min_demand=3, cv2_const=0.0032) -> Tuple[pd.DataFrame, dict]:
    """Randomized search; trial 0 is the textbook pair. Returns (results_df, best_row_dict)."""
    method_by_profile = method_by_profile or DEFAULT_METHOD_BY_PROFILE
    rng = np.random.default_rng(random_state)
    cands = [textbook] + [(float(rng.uniform(*cv2_range)), float(rng.uniform(*adi_range))) for _ in range(n_iter)]
    total_rev = float(revenue_by_id.sum())
    oracle = {u: min(r["abs_err"], key=r["abs_err"].get) for u, r in bt.items()}
    rows = []
    for i, (tc, ta) in enumerate(cands):
        labels = classify(ind, tc, ta, min_demand, cv2_const)
        lab = dict(zip(ind[id_col], labels))
        routing = {u: method_by_profile[p] for u, p in lab.items()}
        m = aggregate_metrics(bt, routing)
        regular = [u for u, p in lab.items() if p in REGULAR]
        rev_share = float(revenue_by_id.reindex(regular).sum() / total_rev) if total_rev else np.nan
        counts = pd.Series(list(lab.values())).value_counts().to_dict()
        rows.append({"trial": i, "thres_cv2": tc, "thres_adi": ta, **m, "rev_share_regular": rev_share, "n_regular": len(regular),
                     "feasible": (rev_share >= min_revenue_share) and (len(regular) >= min_series),
                     "oracle_agreement": float(np.mean([routing[u] == oracle[u] for u in bt])) if bt else np.nan,
                     **{f"n_{p}": counts.get(p, 0) for p in method_by_profile}})
    res = pd.DataFrame(rows)
    feasible = res[res["feasible"]].sort_values("wmape")
    if feasible.empty:
        raise RuntimeError("no feasible candidate - relax min_revenue_share / min_series or widen the ranges")
    best = feasible.iloc[0].to_dict()
    best["oracle_wmape"] = aggregate_metrics(bt, oracle)["wmape"]
    return res, best


# ---------------------------------------------------------------------------
# business overlays
# ---------------------------------------------------------------------------
def business_overlays(panel: pd.DataFrame, profiles: pd.Series, id_col="unique_id", date_col="ds", target="y",
                      activity_cols: Sequence[str] = ("quantity", "orders"), strategic_min_share=0.08, recent_months=12) -> pd.DataFrame:
    """profile -> profile_cluster with strategic > possible_obsolete > new_expansion > SBC profile."""
    rev = panel.groupby(id_col)[target].sum()
    share = rev / rev.sum()
    active = panel[target].fillna(0) != 0
    for c in activity_cols:
        if c in panel:
            active = active | (panel[c].fillna(0) > 0)
    data_max = panel[date_col].max()
    recent = panel[date_col] >= data_max - pd.DateOffset(months=recent_months - 1)
    act = pd.DataFrame({id_col: panel[id_col], "recent": active & recent, "older": active & ~recent}).groupby(id_col).any()
    out = pd.DataFrame({id_col: profiles.index, "profile": profiles.values}).set_index(id_col)
    out["revenue_share"] = share.reindex(out.index).fillna(0.0)
    out = out.join(act, how="left").fillna({"recent": False, "older": False})
    out["profile_cluster"] = out["profile"]
    out.loc[out["recent"] & ~out["older"], "profile_cluster"] = "new_expansion"
    out.loc[~out["recent"] & out["older"], "profile_cluster"] = "possible_obsolete"
    out.loc[out["revenue_share"] >= strategic_min_share, "profile_cluster"] = "strategic"
    return out.drop(columns=["recent", "older"]).reset_index()


def narrate_search(results: pd.DataFrame, best: dict) -> str:
    tb = results.iloc[0]
    unc = results.sort_values("wmape").iloc[0]
    lines = [f"Textbook (0.49 / 1.32): portfolio WMAPE {tb['wmape']:.1f}% with {tb['rev_share_regular']:.0%} of revenue in the regular group "
             f"({'feasible' if tb['feasible'] else 'INFEASIBLE under the guardrail'}).",
             f"Best feasible: CV2 {best['thres_cv2']:.2f} / ADI {best['thres_adi']:.2f} -> WMAPE {best['wmape']:.1f}% "
             f"({best['rev_share_regular']:.0%} of revenue regular, {int(best['n_regular'])} series); routes {best['oracle_agreement']:.0%} "
             f"of series to their best simple method (oracle floor {best['oracle_wmape']:.1f}%)."]
    if not unc["feasible"]:
        lines.append(f"Unconstrained optimum CV2 {unc['thres_cv2']:.2f} / ADI {unc['thres_adi']:.2f} would score {unc['wmape']:.1f}% but leaves only "
                     f"{unc['rev_share_regular']:.0%} of revenue in the regular group - rejected by the guardrail.")
    return "\n".join(lines)
