"""Explainability + business-scenario waterfall for a quantile-blend forecast.

Local explainability (exact)
----------------------------
The blend ``w*q_lo + (1-w)*q_hi`` is linear in two LightGBM quantile models and TreeSHAP
contributions (``pred_contrib=True``) are additive, so the blend's attribution is EXACT:
``blend = baseline + sum(feature contributions)``. Contributions are rolled up into a few
business drivers (recent level, last year, calendar); the identity features (which series)
are folded into the baseline (they say WHICH series, not WHAT changed). A "not modelled"
bar reconciles to the published number (seasonal-naive series, rule lifts) and a "booked
actual" bar carries the realised months, so the waterfall ends on the full quarter.

Business scenario (no model magic)
----------------------------------
The business states an expected price change and quantity change per group; the upside
factor follows from the identity revenue = price x quantity:
``factor = (1 + price_surge) * (1 + qty_surge)``, applied to the NOT-YET-BOOKED months only.
The delta is split into its price and quantity parts by log shares (exact for the product
form), so the scenario is fully attributable to the stated assumptions - the model does not
supply the upside, it only reprices it.

Public API
----------
- ``blend_contributions``   : exact per-row SHAP of the blend (needs the fitted quantile models)
- ``rollup_drivers``        : contributions -> driver groups per aggregate
- ``waterfall_steps``       : tidy steps (step_order, step, measure, value, running_total, is_what_if)
- ``scenario_factor``, ``scenario_attribution``
- ``plot_waterfall``        : plotly figure from the steps (optional dependency)
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

DEFAULT_GROUPS = {"recent level (lag 2-3)": ["y_lag2", "y_lag3"], "last year (lag 12)": ["y_lag12"],
                  "seasonality / calendar": ["fiscal_month", "fiscal_quarter", "quarter_end", "fy_end", "days_in_month"]}
DEFINITIONS = {
    "baseline": "the model's expected value for these series before any recent or seasonal signal: the average training level plus "
                "each series' own identity",
    "recent level (lag 2-3)": "how far the last observed months (2 and 3 months before the forecast month) sit above or below the baseline "
                              "- the run-rate / momentum effect",
    "last year (lag 12)": "how the same month one year earlier pulls the forecast up or down - the year-over-year anchor",
    "seasonality / calendar": "fiscal month and quarter position, quarter-end / year-end effects, days in month - the recurring calendar pattern",
    "not modelled by SHAP": "part of the published number the quantile models do not produce: seasonal-naive series of untuned clusters plus rule lifts",
    "booked actual": "months of the served quarter already realised, carried at their actual value",
    "what-if surge": "business-stated assumption (price and/or quantity change) applied to the forecast months only; revenue = price x quantity",
}


def blend_contributions(models_by_q: Dict[float, object], blend: dict, X: pd.DataFrame, feature_names: Sequence[str]) -> pd.DataFrame:
    """Exact per-row SHAP of w*q_lo + (1-w)*q_hi: weighted sum of the two models' TreeSHAP. Last column = baseline."""
    out = None
    for q, wq in ((blend["q_lo"], blend["w"]), (blend["q_hi"], 1.0 - blend["w"])):
        c = models_by_q[q].predict(X[list(feature_names)], pred_contrib=True) * wq
        out = c if out is None else out + c
    return pd.DataFrame(out, columns=list(feature_names) + ["_baseline"], index=X.index)


def rollup_drivers(contrib: pd.DataFrame, by: pd.Series, groups: Optional[Dict[str, List[str]]] = None,
                   baseline_features: Sequence[str] = ()) -> pd.DataFrame:
    """Sum contributions per aggregate (``by`` aligned with contrib.index) into driver groups; identity features fold into the baseline."""
    groups = groups or DEFAULT_GROUPS
    rows = []
    for key, g in contrib.groupby(by.values):
        row = {"group": key, "baseline": float(g["_baseline"].sum() + g[[c for c in baseline_features if c in g.columns]].sum().sum()),
               "n_rows": int(len(g))}
        for name, cols in groups.items():
            row[name] = float(g[[c for c in cols if c in g.columns]].sum().sum())
        row["blend_shap"] = float(g.drop(columns=["_baseline"]).sum().sum() + g["_baseline"].sum())
        rows.append(row)
    return pd.DataFrame(rows)


def scenario_factor(price_surge: float, qty_surge: float) -> float:
    return (1.0 + price_surge) * (1.0 + qty_surge)


def scenario_attribution(blend_unbooked: float, price_surge: float, qty_surge: float) -> Dict[str, float]:
    """Delta vs blend on the unbooked months, split into price and quantity parts by log shares."""
    f = scenario_factor(price_surge, qty_surge)
    delta = blend_unbooked * (f - 1.0)
    lp, lq = np.log1p(price_surge), np.log1p(qty_surge)
    tot = lp + lq
    p_share = lp / tot if tot != 0 else 0.5
    return {"factor": f, "delta": delta, "delta_from_price": delta * p_share, "delta_from_qty": delta * (1 - p_share), "price_share": p_share}


def waterfall_steps(driver_row: dict, groups: Sequence[str], published_unbooked: float, booked_actual: float, quarter_label: str,
                    scenario: Optional[dict] = None) -> pd.DataFrame:
    """Tidy waterfall: baseline -> drivers -> not modelled -> forecast months (total) -> booked -> full quarter (total) [-> price -> qty -> scenario].

    ``driver_row`` from :func:`rollup_drivers`; ``scenario`` = {'name', 'price_surge', 'qty_surge'} applied to published_unbooked.
    """
    steps = [("baseline", "absolute", float(driver_row["baseline"]), False)]
    steps += [(g, "relative", float(driver_row[g]), False) for g in groups]
    steps.append(("not modelled by SHAP", "relative", float(published_unbooked - driver_row["blend_shap"]), False))
    steps.append(("forecast months", "total", float(published_unbooked), False))
    steps.append(("booked actual", "relative", float(booked_actual), False))
    steps.append((f"{quarter_label} published (full quarter)", "total", float(published_unbooked + booked_actual), False))
    if scenario:
        att = scenario_attribution(published_unbooked, scenario["price_surge"], scenario["qty_surge"])
        steps.append((f"price surge {scenario['price_surge']:+.0%}", "relative", att["delta_from_price"], True))
        steps.append((f"qty surge {scenario['qty_surge']:+.0%}", "relative", att["delta_from_qty"], True))
        steps.append((f"{scenario['name']} scenario", "total", float(published_unbooked * att["factor"] + booked_actual), False))
    rows, running = [], 0.0
    for i, (label, meas, val, what_if) in enumerate(steps):
        running = val if meas in ("absolute", "total") else running + val
        rows.append({"step_order": i, "step": label, "measure": meas, "value": val, "running_total": running, "is_what_if": what_if,
                     "definition": DEFINITIONS.get("what-if surge" if what_if else label.split(" (")[0], None)})
    return pd.DataFrame(rows)


def plot_waterfall(steps: pd.DataFrame, title: str = "", unit_div: float = 1e6, unit: str = "M"):
    """Plotly waterfall with hatched what-if bars (business input, outside the model)."""
    import plotly.graph_objects as go

    fig = go.Figure(go.Waterfall(orientation="v", measure=steps["measure"].tolist(), x=steps["step"].tolist(),
                                 y=[v if m != "total" else 0.0 for v, m in zip(steps["value"], steps["measure"])],
                                 text=[f"{v / unit_div:,.1f}{unit}" for v in steps["value"]], textposition="outside",
                                 increasing=dict(marker=dict(color="#2ca02c")), decreasing=dict(marker=dict(color="#d62728")),
                                 totals=dict(marker=dict(color="#1f77b4")), connector={"line": {"color": "#888", "width": 1}}))
    wi = steps[steps["is_what_if"]]
    if len(wi):
        base = wi["running_total"] - wi["value"]
        fig.add_trace(go.Bar(x=wi["step"], y=wi["value"].abs(), base=base + np.minimum(wi["value"], 0.0), name="what-if (business input)",
                             marker=dict(color="white", pattern=dict(shape="/", fgcolor="#ff7f0e", solidity=0.45), line=dict(color="#ff7f0e", width=2))))
    fig.update_layout(template="plotly_white", title=title, barmode="overlay", showlegend=len(wi) > 0, height=520, width=1000, yaxis_title="value")
    return fig
