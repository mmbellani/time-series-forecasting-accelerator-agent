"""Recency weighting with a surge gate (notebook 10 as a module).

Trees cannot predict above the range they were trained on, and a model fitted on five years
anchors its quantiles to the old level. The cheapest lever is to weight recent months more
when fitting: ``w = 0.5 ** (months_ago / halflife)``. The field lessons this module encodes:

* recency helps series with a SUSTAINED level step-up and hurts seasonal / spiky ones
  -> A/B it per cluster and per series, never adopt it globally;
* a hard training window is worse than a soft half-life;
* the raw size of a surge does not predict the benefit (a one-off spike also looks like a
  surge) -> GATE the weighting: apply it only where the step-up is sustained;
* LightGBM's quantile objective misbehaves with un-normalised sample weights -> every
  weight vector is returned on a mean-1 scale.

All weight functions share the signature ``fn(train_frame, origin) -> np.ndarray`` expected by
``QuantileBlendEngine.train(weight_fn=...)`` (skill forecasting-lightgbm-quantile).
"""
from __future__ import annotations

from typing import Callable, Dict, Optional, Sequence

import numpy as np
import pandas as pd


def months_ago(tr: pd.DataFrame, origin: pd.Timestamp, date_col="ds") -> np.ndarray:
    return ((origin.year - tr[date_col].dt.year) * 12 + (origin.month - tr[date_col].dt.month)).clip(lower=0).to_numpy(float)


def normalize(w: np.ndarray) -> np.ndarray:
    w = np.asarray(w, float)
    return w / w.mean() if w.size and w.mean() > 0 else w


def halflife_weights(tr: pd.DataFrame, origin: pd.Timestamp, halflife: float = 9.0, date_col="ds") -> np.ndarray:
    return normalize(np.power(0.5, months_ago(tr, origin, date_col) / halflife))


def window_weights(tr: pd.DataFrame, origin: pd.Timestamp, window: int = 18, date_col="ds") -> np.ndarray:
    """Hard cut: the last ``window`` months at 1, older rows ~0. Kept as the anti-pattern to compare against."""
    return normalize(np.where(months_ago(tr, origin, date_col) < window, 1.0, 1e-3))


def surge_flags(tr: pd.DataFrame, origin: pd.Timestamp, ratio: float = 1.30, min_months: int = 18, id_col="unique_id",
                date_col="ds", target="y") -> Dict[str, bool]:
    """{series: sustained step-up as of origin}. Leak-free when ``tr`` holds rows <= origin only.

    Step-up = mean(last 6) >= ratio x mean(months -18..-6) AND mean(last 3) >= 0.8 x mean(last 6)
    (a spike that already reverted does not qualify).
    """
    flags = {}
    for uid, g in tr.groupby(id_col, sort=False, observed=True):
        yv = g.sort_values(date_col)[target].to_numpy(float)
        if len(yv) < min_months:
            flags[uid] = False
            continue
        recent6, recent3, prior = np.nanmean(yv[-6:]), np.nanmean(yv[-3:]), np.nanmean(yv[-18:-6])
        flags[uid] = bool(prior > 0 and recent6 / prior >= ratio and recent3 >= 0.8 * recent6)
    return flags


def gated_halflife_weights(tr: pd.DataFrame, origin: pd.Timestamp, halflife: float = 9.0, ratio: float = 1.30,
                           min_months: int = 18, id_col="unique_id", date_col="ds", target="y") -> np.ndarray:
    """Half-life weights only for series flagged by ``surge_flags``; uniform weights elsewhere."""
    flags = surge_flags(tr, origin, ratio, min_months, id_col, date_col, target)
    w = np.power(0.5, months_ago(tr, origin, date_col) / halflife)
    gated = tr[id_col].map(flags).fillna(False).to_numpy(bool)
    return normalize(np.where(gated, w, 1.0))


def make_weight_fn(scheme: Optional[str], **kw) -> Optional[Callable]:
    """'uniform' | 'hl<N>' | 'window<N>' | 'hl<N>_gated' -> weight function (or None for uniform)."""
    if scheme in (None, "uniform"):
        return None
    if scheme.startswith("window"):
        n = int(scheme[6:])
        return lambda tr, o: window_weights(tr, o, n, **kw)
    gated = scheme.endswith("_gated")
    h = float(scheme.replace("_gated", "")[2:])
    if gated:
        return lambda tr, o: gated_halflife_weights(tr, o, h, **kw)
    return lambda tr, o: halflife_weights(tr, o, h, **kw)


def ab_table(results: Sequence[dict]) -> pd.DataFrame:
    """rows of {'cluster','scheme','wmape','bias_pct',...} -> table with delta vs uniform per cluster."""
    ab = pd.DataFrame(results)
    base = ab[ab["scheme"] == "uniform"].set_index("cluster")["wmape"]
    ab["delta_vs_uniform"] = ab["wmape"] - ab["cluster"].map(base)
    return ab


def recommend(ab: pd.DataFrame, min_gain_pts: float = 0.5, max_bias_worsening: float = 5.0) -> pd.DataFrame:
    """Per cluster: the lowest-WMAPE scheme that beats uniform by >= min_gain_pts without worsening |bias| by more than max_bias_worsening."""
    rows = []
    for clu, g in ab.groupby("cluster"):
        base = g[g["scheme"] == "uniform"].iloc[0]
        cand = g[(g["wmape"] < base["wmape"] - min_gain_pts) & (g["bias_pct"].abs() <= abs(base["bias_pct"]) + max_bias_worsening)]
        pick = cand.sort_values("wmape").iloc[0] if len(cand) else base
        rows.append({"cluster": clu, "recommended_scheme": pick["scheme"], "uniform_wmape": base["wmape"], "recommended_wmape": pick["wmape"],
                     "gain_pts": base["wmape"] - pick["wmape"], "recommended_bias": pick["bias_pct"]})
    return pd.DataFrame(rows)


def narrate(rec: pd.DataFrame) -> str:
    lines = []
    for r in rec.itertuples(index=False):
        if r.recommended_scheme == "uniform":
            lines.append(f"{r.cluster}: keep uniform weights (no scheme beat it under the bias guard).")
        else:
            lines.append(f"{r.cluster}: adopt '{r.recommended_scheme}' - WMAPE {r.uniform_wmape:.1f} -> {r.recommended_wmape:.1f} "
                         f"({r.gain_pts:.1f} pts), bias {r.recommended_bias:+.1f}%.")
    return "\n".join(lines)
