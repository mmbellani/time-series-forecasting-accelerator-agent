"""LightGBM quantile blend engine (notebook 09 as a reusable module).

One LightGBM per (cluster, quantile) on LEAK-FREE, ORIGIN-CONSISTENT features; quantile
rearrangement so the grid never crosses; a tuned blend ``w*q_lo + (1-w)*q_hi`` per cluster
with a bias cap; an optional price/quantity rules layer committed only when it beats both
the plain blend AND the seasonal naive AS SERVED; folds anchored to the last data month.

Key ideas encoded
-----------------
* ``lag1`` is excluded: when a quarter is forecast at its origin the previous month is
  unknown for months 2-3. Lags that fall beyond the origin are replaced by the last actual.
* ``served_rows`` rebuilds every target month exactly as production will see it (strict
  mode); ``mode='readable'`` uses the realised rows (contemporaneous drivers) - the two
  scores differ, and the strict one is what production will see.
* Tiny regularised trees for a single-series cluster keep the quantiles monotonic; the
  remaining crossings are removed by sorting the quantiles within each row.
* Blend tuning is restricted to the series that make up ``top_share`` of revenue and to
  candidates whose net bias is within ``bias_cap``.
* Sample weights (recency) are normalised to mean 1 - the quantile objective misbehaves
  with raw-scale weights.

Column contract: ``unique_id``, ``ds`` (month start), ``y``, a cluster column, optional
``quantity`` / ``price_per_unit`` (rules drivers), categorical identity columns.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

try:  # LightGBM is only needed for training
    import lightgbm as lgb
except Exception:  # pragma: no cover
    lgb = None


DEFAULT_QGRID = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95]
SINGLE_SERIES_PARAMS = {"n_estimators": 250, "learning_rate": 0.05, "num_leaves": 3, "max_depth": 4, "min_child_samples": 10,
                        "reg_alpha": 0.5, "reg_lambda": 2.5, "subsample": 0.7, "subsample_freq": 1, "colsample_bytree": 0.9,
                        "min_split_gain": 0.05}
POOLED_PARAMS = {"n_estimators": 500, "learning_rate": 0.02, "num_leaves": 15, "min_child_samples": 20,
                 "reg_alpha": 2.0, "reg_lambda": 10.0, "subsample": 0.8, "subsample_freq": 1, "colsample_bytree": 0.8}


def qcol(q: float) -> str:
    return f"q{int(round(q * 100))}"


def wmape(a, p) -> float:
    a, p = np.asarray(a, float), np.asarray(p, float)
    m = ~np.isnan(a) & ~np.isnan(p)
    d = np.abs(a[m]).sum()
    return np.nan if d == 0 else float(100.0 * np.abs(a[m] - p[m]).sum() / d)


def bias_pct(a, p) -> float:
    a, p = np.asarray(a, float), np.asarray(p, float)
    m = ~np.isnan(a) & ~np.isnan(p)
    d = np.abs(a[m]).sum()
    return np.nan if d == 0 else float(100.0 * (p[m] - a[m]).sum() / d)


# ---------------------------------------------------------------------------
# fiscal calendar + folds anchored to the last data month
# ---------------------------------------------------------------------------
def fiscal_parts(ts: pd.Timestamp, fy_start_month: int):
    fm = ((ts.month - fy_start_month) % 12) + 1
    return ts.year + (1 if ts.month >= fy_start_month else 0), (fm - 1) // 3 + 1, fm


def fq_label(ts: pd.Timestamp, fy_start_month: int) -> str:
    fy, fq, _ = fiscal_parts(ts, fy_start_month)
    return f"FY{fy % 100:02d}-Q{fq}"


def make_folds(data_max: pd.Timestamp, n_val: int, fy_start_month: int) -> List[dict]:
    """Validation = last n_val COMPLETE fiscal quarters; served = rest of the current quarter, or the next one at a boundary."""
    def miq(ts):
        return ((fiscal_parts(ts, fy_start_month)[2] - 1) % 3) + 1

    def qstart(ts):
        return ts.replace(day=1) - pd.DateOffset(months=miq(ts) - 1)

    cur, m = qstart(data_max), miq(data_max)
    last_complete = cur if m == 3 else cur - pd.DateOffset(months=3)
    folds = []
    for i in range(n_val, 0, -1):
        qs = last_complete - pd.DateOffset(months=3 * (i - 1))
        folds.append({"name": f"fold{n_val - i + 1}", "quarter": fq_label(qs, fy_start_month), "origin": qs - pd.DateOffset(months=1),
                      "months": [qs + pd.DateOffset(months=j) for j in range(3)], "future": False})
    if m == 3:
        served = [cur + pd.DateOffset(months=3 + j) for j in range(3)]
    else:
        served = [cur + pd.DateOffset(months=j) for j in range(3) if cur + pd.DateOffset(months=j) > data_max]
    folds.append({"name": "final", "quarter": fq_label(served[0], fy_start_month), "origin": data_max, "months": served, "future": True})
    return folds


# ---------------------------------------------------------------------------
# the engine
# ---------------------------------------------------------------------------
@dataclass
class QuantileBlendEngine:
    panel: pd.DataFrame
    cluster_col: str = "profile_cluster"
    tune_clusters: Sequence[str] = ("strategic", "smooth", "erratic")
    cats: Sequence[str] = ("product_group", "region", "channel")
    id_col: str = "unique_id"
    date_col: str = "ds"
    target: str = "y"
    qty_col: str = "quantity"
    price_col: str = "price_per_unit"
    fy_start_month: int = 10
    season: int = 12
    qgrid: Sequence[float] = tuple(DEFAULT_QGRID)
    params: Dict[str, dict] = field(default_factory=dict)
    extrap_window: int = 6
    random_state: int = 42
    rearrange: bool = True

    def __post_init__(self):
        p = self.panel.sort_values([self.id_col, self.date_col]).drop_duplicates([self.id_col, self.date_col], keep="last").copy()
        p[self.date_col] = pd.to_datetime(p[self.date_col])
        if self.price_col not in p.columns and self.qty_col in p.columns:
            p[self.price_col] = p[self.target] / p[self.qty_col].replace(0, np.nan)
        self.cal_features = ["fiscal_month", "fiscal_quarter", "quarter_end", "fy_end", "days_in_month"]
        p[self.cal_features] = self.calendar_features(p[self.date_col])
        g = p.groupby(self.id_col, sort=False)
        for k in (2, 3, 12):
            p[f"y_lag{k}"] = g[self.target].shift(k)
        if self.price_col in p.columns:
            p["price_qoq"] = g[self.price_col].pct_change(3, fill_method=None)
        if self.qty_col in p.columns:
            p["qty_qoq"] = g[self.qty_col].pct_change(3, fill_method=None)
        self.cat_levels = {c: sorted(p[c].dropna().astype(str).unique()) for c in self.cats}
        for c in self.cats:
            p[c] = pd.Categorical(p[c].astype(str), categories=self.cat_levels[c])
        self.feat = p
        self.model_features = self.cal_features + ["y_lag2", "y_lag3", "y_lag12"] + list(self.cats)
        self.data_max = p[self.date_col].max()
        self.actual = p.set_index([self.id_col, self.date_col])[self.target]
        self.base = {"objective": "quantile", "boosting_type": "gbdt", "verbose": -1, "n_jobs": -1, "random_state": self.random_state}

    # ---- features -------------------------------------------------------
    def calendar_features(self, dates: pd.Series) -> pd.DataFrame:
        fm = ((dates.dt.month - self.fy_start_month) % 12) + 1
        return pd.DataFrame({"fiscal_month": fm, "fiscal_quarter": (fm - 1) // 3 + 1, "quarter_end": fm.isin([3, 6, 9, 12]).astype(int),
                             "fy_end": (fm == 12).astype(int), "days_in_month": dates.dt.days_in_month}, index=dates.index)

    def params_for(self, cluster: str) -> dict:
        if cluster in self.params:
            return self.params[cluster]
        n_series = self.feat.loc[self.feat[self.cluster_col] == cluster, self.id_col].nunique()
        return SINGLE_SERIES_PARAMS if n_series <= 3 else POOLED_PARAMS

    # ---- training -------------------------------------------------------
    def train(self, origin: pd.Timestamp, qgrid: Optional[Sequence[float]] = None,
              weight_fn: Optional[Callable[[pd.DataFrame, pd.Timestamp], np.ndarray]] = None,
              params_override: Optional[dict] = None) -> Dict[str, dict]:
        """{cluster: {q: fitted LGBMRegressor}} on rows <= origin. weight_fn(train_frame, origin) -> weights (normalised to mean 1)."""
        if lgb is None:
            raise ImportError("lightgbm is required for training")
        qgrid = list(qgrid or self.qgrid)
        models = {}
        for clu in self.tune_clusters:
            tr = self.feat[(self.feat[self.cluster_col] == clu) & (self.feat[self.date_col] <= origin) & self.feat[self.target].notna()]
            tr = tr.sort_values([self.id_col, self.date_col])
            if tr.empty:
                continue
            w = None
            if weight_fn is not None:
                w = np.asarray(weight_fn(tr, origin), float)
                w = w / w.mean()
            p0 = params_override or self.params_for(clu)
            models[clu] = {q: lgb.LGBMRegressor(**{**self.base, "alpha": float(np.clip(q, 1e-3, 0.999)), **p0})
                           .fit(tr[self.model_features], tr[self.target], sample_weight=w, categorical_feature=list(self.cats)) for q in qgrid}
        return models

    # ---- as-served rows -------------------------------------------------
    def _extrapolate(self, series: pd.Series, upto: pd.Timestamp) -> pd.Series:
        s = series.dropna().sort_index()
        if s.empty:
            return pd.Series(dtype=float)
        diffs = np.diff(s.iloc[-self.extrap_window:].to_numpy(float))
        step = float(np.median(diffs)) if len(diffs) else 0.0
        idx = pd.date_range(s.index.min(), max(s.index.max(), upto), freq="MS")
        path, cur = s.reindex(idx), float(s.iloc[-1])
        for m in idx[idx > s.index.max()]:
            cur = max(cur + step, 0.0)
            path.loc[m] = cur
        return path

    def served_rows(self, cluster: str, months: Sequence[pd.Timestamp], origin: pd.Timestamp) -> pd.DataFrame:
        """Rows for every series of the cluster x target month, built only from history <= origin."""
        cdf = self.feat[(self.feat[self.cluster_col] == cluster) & (self.feat[self.date_col] <= origin) & self.feat[self.target].notna()]
        out = []
        for uid, g in cdf.groupby(self.id_col, sort=False, observed=True):
            g = g.sort_values(self.date_col)
            yv = g.set_index(self.date_col)[self.target]
            last_y, last_row = float(yv.iloc[-1]), g.iloc[-1]
            price = self._extrapolate(g.set_index(self.date_col)[self.price_col], max(months)) if self.price_col in g else pd.Series(dtype=float)
            qty = self._extrapolate(g.set_index(self.date_col)[self.qty_col], max(months)) if self.qty_col in g else pd.Series(dtype=float)
            for m in months:
                def lag(k):
                    d = m - pd.DateOffset(months=k)
                    return float(yv.get(d, last_y)) if d <= origin else last_y

                def qoq(p):
                    a, b = p.get(m, np.nan), p.get(m - pd.DateOffset(months=3), np.nan)
                    return (a - b) / abs(b) if (pd.notna(a) and pd.notna(b) and b != 0) else np.nan
                out.append({self.id_col: uid, self.date_col: m, self.cluster_col: last_row[self.cluster_col],
                            **{c: last_row[c] for c in self.cats}, "y_lag2": lag(2), "y_lag3": lag(3), "y_lag12": lag(12),
                            "price_qoq": qoq(price), "qty_qoq": qoq(qty),
                            "snaive": max(float(yv.get(m - pd.DateOffset(months=self.season), last_y)), 0.0)})
        rows = pd.DataFrame(out)
        if rows.empty:
            return rows
        rows[self.cal_features] = self.calendar_features(rows[self.date_col])
        for c in self.cats:
            rows[c] = pd.Categorical(rows[c].astype(str), categories=self.cat_levels[c])
        return rows

    def build_frame(self, origin: pd.Timestamp, months: Sequence[pd.Timestamp], models: Dict[str, dict], mode: str = "strict") -> pd.DataFrame:
        """Quantile predictions per tuned series x month. mode='strict' (as served) or 'readable' (realised rows)."""
        parts = []
        for clu, qmods in models.items():
            if mode == "readable":
                block = self.feat[(self.feat[self.cluster_col] == clu) & self.feat[self.date_col].isin(months)].copy()
                block["snaive"] = [max(float(self.actual.get((u, d - pd.DateOffset(months=self.season)), 0.0)), 0.0)
                                   for u, d in zip(block[self.id_col], block[self.date_col])]
            else:
                block = self.served_rows(clu, months, origin)
            if block.empty:
                continue
            block["y"] = [self.actual.get((u, d), np.nan) for u, d in zip(block[self.id_col], block[self.date_col])]
            qs = sorted(qmods)
            for q in qs:
                block[qcol(q)] = qmods[q].predict(block[self.model_features])
            if self.rearrange:
                cols = [qcol(q) for q in qs]
                block[cols] = np.sort(block[cols].to_numpy(float), axis=1)
            parts.append(block)
        fc = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        if not fc.empty:
            fc["origin"], fc["mode"], fc["has_actual"] = origin, mode, fc["y"].notna()
        return fc

    def seasonal_naive_all(self, months: Sequence[pd.Timestamp]) -> pd.DataFrame:
        last = self.feat.sort_values(self.date_col).groupby(self.id_col, observed=True)[self.target].last()
        rows = [{self.id_col: u, self.date_col: m,
                 "snaive": max(float(self.actual.get((u, m - pd.DateOffset(months=self.season)), last[u])), 0.0)} for u in last.index for m in months]
        return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# blend, rules, tuning, gate
# ---------------------------------------------------------------------------
def crossing_rate(frame: pd.DataFrame, qgrid: Sequence[float]) -> float:
    P = frame[[qcol(q) for q in qgrid]].to_numpy(float)
    return float((np.diff(P, axis=1) < -1e-9).mean()) if len(P) else np.nan


def apply_blend(fc: pd.DataFrame, blend: dict) -> pd.DataFrame:
    fc = fc.copy()
    fc["yhat_blend"] = blend["w"] * fc[qcol(blend["q_lo"])] + (1.0 - blend["w"]) * fc[qcol(blend["q_hi"])]
    return fc


def apply_rules(fc: pd.DataFrame, rules: dict) -> pd.DataFrame:
    """Up rule: price or qty driver > up_margin (and neither < -up_margin) -> q_hi_rule. Down rule: qty <= -down_margin -> q_lo_rule."""
    fc = fc.copy()
    pq = fc["price_qoq"] if "price_qoq" in fc else pd.Series(np.nan, index=fc.index)
    qq = fc["qty_qoq"] if "qty_qoq" in fc else pd.Series(np.nan, index=fc.index)
    up = (((pq > rules["up_margin"]) | (qq > rules["up_margin"])) & ~((pq < -rules["up_margin"]) | (qq < -rules["up_margin"]))).fillna(False)
    dn = (qq <= -rules["down_margin"]).fillna(False) & ~up
    fc["yhat_rules"] = fc["yhat_blend"]
    fc.loc[up, "yhat_rules"] = fc.loc[up, qcol(rules["q_hi_rule"])]
    fc.loc[dn, "yhat_rules"] = fc.loc[dn, qcol(rules["q_lo_rule"])]
    fc["rule_fired"] = np.where(up, "up", np.where(dn, "down", "none"))
    return fc


def revenue_focus(panel: pd.DataFrame, top_share=0.80, id_col="unique_id", target="y") -> set:
    rev = panel.groupby(id_col, observed=True)[target].sum().sort_values(ascending=False)
    return set(rev.index[(rev.cumsum() / rev.sum()).shift(fill_value=0.0) < top_share])


def pooled_score(frames: Sequence[pd.DataFrame], cluster: str, col: str, cluster_col="profile_cluster", id_col="unique_id",
                 focus: Optional[set] = None):
    parts = []
    for f in frames:
        s = f[(f[cluster_col].astype(str) == cluster) & f["has_actual"]]
        if focus:
            s = s[s[id_col].astype(str).isin(focus)] if (s[id_col].astype(str).isin(focus)).any() else s
        parts.append(s)
    s = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return (wmape(s["y"], s[col]), bias_pct(s["y"], s[col])) if len(s) else (np.nan, np.nan)


def oracle_wmape(frames: Sequence[pd.DataFrame], cluster: str, qgrid: Sequence[float], cluster_col="profile_cluster") -> float:
    s = pd.concat([f[(f[cluster_col].astype(str) == cluster) & f["has_actual"]] for f in frames], ignore_index=True)
    if s.empty:
        return np.nan
    P, A = s[[qcol(q) for q in qgrid]].to_numpy(float), s["y"].to_numpy(float)
    return wmape(A, P[np.arange(len(s)), np.argmin(np.abs(P - A[:, None]), axis=1)])


def tune_blend(frames: Sequence[pd.DataFrame], cluster: str, focus: Optional[set] = None, bias_cap=0.15,
               lo_grid=(0.2, 0.3, 0.4, 0.5, 0.6, 0.7), hi_grid=(0.6, 0.7, 0.8, 0.9, 0.95), w_grid=(0.2, 0.35, 0.5, 0.65, 0.8),
               cluster_col="profile_cluster") -> dict:
    """Grid search of w*q_lo + (1-w)*q_hi minimising pooled WMAPE under |bias| <= bias_cap. Returns the best blend + diagnostics."""
    cands = []
    for lo, hi, w in itertools.product(lo_grid, hi_grid, w_grid):
        if hi <= lo or any(qcol(q) not in frames[0].columns for q in (lo, hi)):
            continue
        b = {"q_lo": lo, "q_hi": hi, "w": w}
        e, bias = pooled_score([apply_blend(f, b) for f in frames], cluster, "yhat_blend", cluster_col, focus=focus)
        cands.append({**b, "wmape": e, "bias": bias, "eligible": abs(bias) <= bias_cap * 100})
    cands = pd.DataFrame(cands).sort_values("wmape")
    pick = cands[cands["eligible"]].iloc[0] if cands["eligible"].any() else cands.iloc[0]
    return {"blend": {"q_lo": float(pick["q_lo"]), "q_hi": float(pick["q_hi"]), "w": float(pick["w"])}, "wmape": float(pick["wmape"]),
            "bias": float(pick["bias"]), "unconstrained_wmape": float(cands.iloc[0]["wmape"]), "unconstrained_bias": float(cands.iloc[0]["bias"]),
            "candidates": cands}


def commit_gate(strict_frames: Sequence[pd.DataFrame], cluster: str, blend: dict, focus: Optional[set] = None,
                rule_grid: Optional[dict] = None, readable_frames: Optional[Sequence[pd.DataFrame]] = None,
                cluster_col="profile_cluster") -> dict:
    """Rules are committed only if their STRICT WMAPE beats both the plain blend and the seasonal naive."""
    rule_grid = rule_grid or {"up_margin": [0.10, 0.25], "down_margin": [0.25, 0.50], "q_hi_rule": [0.80, 0.90], "q_lo_rule": [0.20, 0.30]}
    best_rules, best_strict = None, np.inf
    for um, dm, qh, ql in itertools.product(*rule_grid.values()):
        rules = dict(zip(rule_grid.keys(), (um, dm, qh, ql)))
        if any(qcol(q) not in strict_frames[0].columns for q in (qh, ql)):
            continue
        e, _ = pooled_score([apply_rules(apply_blend(f, blend), rules) for f in strict_frames], cluster, "yhat_rules", cluster_col, focus=focus)
        if e < best_strict:
            best_rules, best_strict = rules, e
    e_blend, _ = pooled_score([apply_blend(f, blend) for f in strict_frames], cluster, "yhat_blend", cluster_col, focus=focus)
    e_naive, _ = pooled_score(strict_frames, cluster, "snaive", cluster_col, focus=focus)
    out = {"cluster": cluster, "snaive": e_naive, "blend_strict": e_blend, "rules_strict": best_strict, "best_rules": best_rules}
    if readable_frames is not None and best_rules is not None:
        out["blend_readable"], _ = pooled_score([apply_blend(f, blend) for f in readable_frames], cluster, "yhat_blend", cluster_col, focus=focus)
        out["rules_readable"], _ = pooled_score([apply_rules(apply_blend(f, blend), best_rules) for f in readable_frames], cluster, "yhat_rules", cluster_col, focus=focus)
    commit = best_rules is not None and best_strict < e_blend and best_strict < e_naive
    out["method"] = "blend+rules" if commit else ("blend" if e_blend <= e_naive else "seasonal_naive")
    out["rules"] = best_rules if commit else None
    return out


def committed_forecast(fc: pd.DataFrame, committed: Dict[str, dict], cluster_col="profile_cluster") -> pd.DataFrame:
    """Apply each cluster's committed recipe {'method', 'blend', 'rules'} -> yhat_committed + cluster_method."""
    out = []
    for clu, cfg in committed.items():
        s = fc[fc[cluster_col].astype(str) == clu]
        if s.empty:
            continue
        s = apply_blend(s, cfg["blend"])
        if cfg.get("rules"):
            s = apply_rules(s, cfg["rules"])
        else:
            s["yhat_rules"], s["rule_fired"] = s["yhat_blend"], "none"
        s["yhat_committed"] = {"blend+rules": s["yhat_rules"], "blend": s["yhat_blend"], "seasonal_naive": s["snaive"]}[cfg["method"]]
        s["cluster_method"] = cfg["method"]
        out.append(s)
    return pd.concat(out, ignore_index=True) if out else fc.iloc[0:0].copy()
