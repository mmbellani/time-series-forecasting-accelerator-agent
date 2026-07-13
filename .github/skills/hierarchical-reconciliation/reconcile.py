"""Hierarchical forecast reconciliation utilities.

Aggregate **base (bottom-level) forecasts** up a user-defined hierarchy, chart the
roll-up, and diagnose **how forecast values compose** and **how errors propagate** into
the aggregate. Built for the Time Series Forecasting Accelerator pipeline
(LightGBM + mlforecast, notebook 06), whose ``<scenario>_forecasts`` output holds
``unique_id`` (the base series), ``ds`` (date), ``y`` (actual) and one or more
``y_hat_*`` prediction columns. Hierarchy levels are the static attribute columns that
identify where each base series sits (e.g. ``region``, ``segment``, ``product_family``).

This skill sits **downstream** of two sibling skills and hands off to them:

- ``forecast-explainability`` — explains *why* a base node's forecast is what it is
  (feature weights / SHAP). This skill shows *how those base forecasts roll up* into the
  aggregate, so you can attribute an aggregate move to specific nodes and their drivers.
- ``error-analysis`` — computes per-row errors and decomposes them by calendar. This
  skill re-uses that per-row error and shows *how the error propagates* up the hierarchy:
  which nodes drive the aggregate error, and whether errors **cancel** (diversify) or
  **reinforce** (systematic bias) on aggregation.

Reconciliation approach
------------------------
The pipeline produces coherent **bottom-up** forecasts: an aggregate node's forecast is
the sum of its children's base forecasts. Bottom-up is coherent by construction, so the
focus here is *composition* and *error propagation*, not choosing weights. When a
separately-produced aggregate forecast is supplied (e.g. a direct top-level model), the
``coherence_gap`` helper quantifies the incoherence.

Error convention
----------------
Matches the ``error-analysis`` skill (Hyndman residual)::

    error = y_true - y_pred      # actual minus forecast

- ``error > 0`` → **under-forecast**; ``error < 0`` → **over-forecast**.
- ``ME`` (mean error / bias) near 0 means unbiased.

Public API
----------
- ``describe_hierarchy``      : cardinality of each level + node counts (intake helper).
- ``validate_hierarchy``      : check level columns exist and are properly nested.
- ``aggregate_to_level``      : bottom-up sum of ``y``/``y_hat`` to a chosen level.
- ``bottom_up``               : aggregate across *every* level (Total → base) in one frame.
- ``coherence_gap``           : compare bottom-up sum vs a supplied aggregate forecast.
- ``level_contributions``     : each node's share of its parent aggregate.
- ``error_by_level``          : accuracy metrics computed at each aggregation level.
- ``error_contribution``      : each node's signed contribution to the aggregate error.
- ``error_cancellation``      : how much error cancels (diversifies) on aggregation.
- Charts: ``plot_hierarchy_tree``, ``plot_aggregate_actual_vs_forecast``,
  ``plot_level_contributions``, ``plot_contribution_bars``, ``plot_waterfall``,
  ``plot_error_by_level``, ``plot_error_propagation``, ``reconciliation_grid``.
- Narratives: ``narrate_hierarchy``, ``narrate_reconciliation``,
  ``narrate_error_propagation``.

``matplotlib`` is only required for the plotting helpers. The aggregation / metric
functions have no plotting dependency.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

TOTAL_LABEL = "Total"


# ---------------------------------------------------------------------------
# Hierarchy definition & validation
# ---------------------------------------------------------------------------

def describe_hierarchy(df: pd.DataFrame, levels: Sequence[str],
                       base_id: str = "unique_id") -> pd.DataFrame:
    """Summarize a proposed hierarchy so the data scientist can confirm it.

    ``levels`` must be ordered from **top (coarsest)** to **bottom (finest)**; the finest
    level is usually the base series ``base_id``. The returned frame reports, per level,
    the number of distinct nodes and the average number of children per parent — the
    fan-out that determines how much aggregation happens at each step.

    Use this as the *intake* step: present it to the user and confirm the levels and the
    target aggregation level before reconciling.
    """
    levels = list(levels)
    _require_cols(df, levels)
    rows = []
    for i, lvl in enumerate(levels):
        keys = levels[: i + 1]
        n_nodes = df.drop_duplicates(keys).shape[0]
        if i == 0:
            avg_children = float(n_nodes)  # children of the (implicit) Total
            parent = TOTAL_LABEL
        else:
            parent_keys = levels[:i]
            n_parents = df.drop_duplicates(parent_keys).shape[0]
            avg_children = n_nodes / n_parents if n_parents else float("nan")
            parent = levels[i - 1]
        rows.append({
            "level": lvl,
            "depth": i + 1,
            "parent_level": parent,
            "n_nodes": int(n_nodes),
            "avg_children_per_parent": round(avg_children, 2),
        })
    # Prepend the implicit grand-total level for completeness.
    total_row = {"level": TOTAL_LABEL, "depth": 0, "parent_level": "-",
                 "n_nodes": 1, "avg_children_per_parent": 1.0}
    return pd.DataFrame([total_row] + rows)


def validate_hierarchy(df: pd.DataFrame, levels: Sequence[str],
                       base_id: str = "unique_id") -> Dict[str, object]:
    """Validate that ``levels`` form a properly nested hierarchy.

    Checks that every column exists and that each child belongs to exactly one parent
    (strict nesting). Returns a dict with ``ok`` (bool) and ``issues`` (list of strings).
    A non-nested level (a child mapping to several parents) is reported but not raised —
    some hierarchies are naturally *grouped* rather than strictly nested.
    """
    levels = list(levels)
    _require_cols(df, levels)
    issues: List[str] = []
    for i in range(1, len(levels)):
        child_keys = levels[: i + 1]
        parent_keys = levels[:i]
        # Each unique child-node should map to a single parent-node.
        mapping = df.drop_duplicates(child_keys)[child_keys]
        counts = mapping.groupby(levels[i]).apply(
            lambda g: g[parent_keys].drop_duplicates().shape[0]
        )
        offenders = counts[counts > 1]
        if not offenders.empty:
            issues.append(
                f"Level '{levels[i]}' is not strictly nested under "
                f"{parent_keys}: {len(offenders)} node(s) map to >1 parent "
                f"(e.g. {list(offenders.index[:3])}). Treated as a grouped dimension."
            )
    return {"ok": len(issues) == 0, "issues": issues, "levels": levels}


# ---------------------------------------------------------------------------
# Bottom-up aggregation
# ---------------------------------------------------------------------------

def _agg_keys(levels: Sequence[str], level: str) -> List[str]:
    """Return the grouping columns from the top down to (and including) ``level``."""
    levels = list(levels)
    if level == TOTAL_LABEL:
        return []
    if level not in levels:
        raise KeyError(f"Level '{level}' is not in the hierarchy {levels}.")
    return levels[: levels.index(level) + 1]


def aggregate_to_level(df: pd.DataFrame, levels: Sequence[str], level: str,
                       date_col: str = "ds", y_true: str = "y", y_pred: str = "y_hat",
                       node_sep: str = " | ") -> pd.DataFrame:
    """Bottom-up sum of actuals and forecasts up to a chosen aggregation ``level``.

    For each date, sum ``y_true`` and ``y_pred`` over all base series that share the same
    values of the grouping columns ``levels[:level]``. Passing ``level="Total"`` collapses
    everything into a single aggregate series.

    Returns a tidy frame with columns: ``node`` (the aggregated node label), the grouping
    key columns, ``date_col``, ``y_true``, ``y_pred``, and ``level``.
    """
    keys = _agg_keys(levels, level)
    group_cols = keys + [date_col]

    if keys:
        agg = df.groupby(group_cols, dropna=False)[[y_true, y_pred]].sum().reset_index()
        agg["node"] = agg[keys].astype(str).agg(node_sep.join, axis=1)
    else:
        agg = df.groupby([date_col], dropna=False)[[y_true, y_pred]].sum().reset_index()
        agg["node"] = TOTAL_LABEL

    agg["level"] = level
    front = ["node"] + keys + [date_col, y_true, y_pred, "level"]
    return agg[front]


def bottom_up(df: pd.DataFrame, levels: Sequence[str],
              date_col: str = "ds", y_true: str = "y", y_pred: str = "y_hat",
              include_total: bool = True) -> pd.DataFrame:
    """Aggregate base forecasts across **every** level in one long frame.

    Produces, for each level from ``Total`` down to the base level, the bottom-up
    actual/forecast time series per node. Handy for level-by-level charts and for
    ``error_by_level``.
    """
    levels = list(levels)
    order = ([TOTAL_LABEL] if include_total else []) + levels
    frames = [
        aggregate_to_level(df, levels, lvl, date_col, y_true, y_pred)
        for lvl in order
    ]
    out = pd.concat(frames, ignore_index=True)
    out["level"] = pd.Categorical(out["level"], categories=order, ordered=True)
    return out


def coherence_gap(base_df: pd.DataFrame, agg_forecast: pd.DataFrame, levels: Sequence[str],
                  level: str, date_col: str = "ds", y_pred: str = "y_hat",
                  agg_pred: str = "y_hat") -> pd.DataFrame:
    """Quantify incoherence between the bottom-up sum and a supplied aggregate forecast.

    When a level was forecast *directly* (not by summing children), the two need not
    agree. This returns, per node and date, the bottom-up sum, the direct aggregate
    forecast, and the ``gap = direct - bottom_up``. A large systematic gap signals the
    two models disagree and reconciliation (e.g. MinT) would be needed.
    """
    keys = _agg_keys(levels, level)
    bu = aggregate_to_level(base_df, levels, level, date_col, y_true=y_pred, y_pred=y_pred)
    bu = bu.rename(columns={y_pred: "bottom_up"})[["node", date_col, "bottom_up"]]

    direct = agg_forecast.copy()
    if keys and "node" not in direct.columns:
        direct["node"] = direct[keys].astype(str).agg(" | ".join, axis=1)
    elif not keys and "node" not in direct.columns:
        direct["node"] = TOTAL_LABEL
    direct = direct[["node", date_col, agg_pred]].rename(columns={agg_pred: "direct"})

    merged = bu.merge(direct, on=["node", date_col], how="outer")
    merged["gap"] = merged["direct"] - merged["bottom_up"]
    return merged


# ---------------------------------------------------------------------------
# Composition: how nodes build the aggregate
# ---------------------------------------------------------------------------

def level_contributions(df: pd.DataFrame, levels: Sequence[str], level: str,
                        date_col: str = "ds", y_true: str = "y", y_pred: str = "y_hat",
                        value: str = "y_pred", period: Optional[object] = None) -> pd.DataFrame:
    """Each node's share of the aggregate at ``level`` (forecast composition).

    ``value`` selects which quantity to decompose (``"y_pred"`` or ``"y_true"``).
    When ``period`` is given (a value of ``date_col``) the share is computed for that
    single period; otherwise it is the share of the total-over-time. Returns nodes sorted
    by descending share with columns ``node``, ``value``, ``share_pct``, ``cum_share_pct``.
    """
    col = y_pred if value == "y_pred" else y_true
    agg = aggregate_to_level(df, levels, level, date_col, y_true, y_pred)
    if period is not None:
        agg = agg[agg[date_col] == period]
    grp = agg.groupby("node", dropna=False)[col].sum().reset_index(name="value")
    total = grp["value"].sum()
    grp = grp.sort_values("value", ascending=False).reset_index(drop=True)
    grp["share_pct"] = np.where(total != 0, grp["value"] / total * 100.0, np.nan)
    grp["cum_share_pct"] = grp["share_pct"].cumsum()
    return grp


# ---------------------------------------------------------------------------
# Error metrics (aligned with the error-analysis skill)
# ---------------------------------------------------------------------------

def _metrics_from_arrays(actual: np.ndarray, pred: np.ndarray) -> Dict[str, float]:
    actual = np.asarray(actual, dtype=float)
    pred = np.asarray(pred, dtype=float)
    error = actual - pred
    abs_error = np.abs(error)
    n = len(error)
    if n == 0:
        return {"n": 0, "ME": np.nan, "MAE": np.nan, "RMSE": np.nan,
                "MAPE": np.nan, "WMAPE": np.nan}
    valid = actual != 0
    ape = np.where(valid, abs_error / np.abs(actual), np.nan)
    total_actual = np.abs(actual).sum()
    wmape = abs_error.sum() / total_actual if total_actual != 0 else np.nan
    return {
        "n": int(n),
        "ME": float(np.mean(error)),
        "MAE": float(np.mean(abs_error)),
        "RMSE": float(np.sqrt(np.mean(error ** 2))),
        "MAPE": float(np.nanmean(ape) * 100.0),
        "WMAPE": float(wmape * 100.0) if wmape == wmape else np.nan,
    }


def error_by_level(df: pd.DataFrame, levels: Sequence[str],
                   date_col: str = "ds", y_true: str = "y", y_pred: str = "y_hat",
                   include_total: bool = True) -> pd.DataFrame:
    """Accuracy metrics computed on the aggregated series at **each** level.

    This is the core error-propagation view: as you move up the hierarchy, random errors
    tend to cancel (MAPE / WMAPE fall) while systematic bias accumulates (ME grows in
    magnitude). Returns one row per level with ``n``, ``ME``, ``MAE``, ``RMSE``,
    ``MAPE`` (%), ``WMAPE`` (%), ordered Total → base.
    """
    levels = list(levels)
    order = ([TOTAL_LABEL] if include_total else []) + levels
    rows = []
    for lvl in order:
        agg = aggregate_to_level(df, levels, lvl, date_col, y_true, y_pred)
        m = _metrics_from_arrays(agg[y_true].values, agg[y_pred].values)
        rows.append({"level": lvl, **m})
    out = pd.DataFrame(rows)
    out["level"] = pd.Categorical(out["level"], categories=order, ordered=True)
    return out.sort_values("level").reset_index(drop=True)


def error_contribution(df: pd.DataFrame, levels: Sequence[str], level: str,
                       date_col: str = "ds", y_true: str = "y", y_pred: str = "y_hat",
                       top_n: Optional[int] = None) -> pd.DataFrame:
    """Each node's **signed** contribution to the parent aggregate error.

    The aggregate error at a level equals the sum of its children's signed errors, so this
    decomposes *who* drives the aggregate miss and *in which direction*. A node with large
    positive error (under-forecast) can be offset by another with negative error
    (over-forecast) — that cancellation is exactly what ``error_cancellation`` quantifies.

    Returns columns ``node``, ``sum_error`` (signed), ``sum_abs_error``,
    ``share_of_abs_pct`` (share of gross error), ``net_share_pct`` (share of the *net*
    aggregate error), sorted by gross magnitude.
    """
    agg = aggregate_to_level(df, levels, level, date_col, y_true, y_pred)
    agg = agg.assign(error=agg[y_true] - agg[y_pred])
    grp = agg.groupby("node", dropna=False)["error"].agg(
        sum_error="sum", sum_abs_error=lambda s: s.abs().sum()
    ).reset_index()
    gross = grp["sum_abs_error"].sum()
    net = grp["sum_error"].sum()
    grp["share_of_abs_pct"] = np.where(gross != 0, grp["sum_abs_error"] / gross * 100.0, np.nan)
    grp["net_share_pct"] = np.where(net != 0, grp["sum_error"] / net * 100.0, np.nan)
    grp = grp.sort_values("sum_abs_error", ascending=False).reset_index(drop=True)
    if top_n is not None:
        grp = grp.head(top_n)
    return grp


def error_cancellation(df: pd.DataFrame, levels: Sequence[str],
                       date_col: str = "ds", y_true: str = "y", y_pred: str = "y_hat",
                       include_total: bool = True) -> pd.DataFrame:
    """Quantify how much forecast error **cancels** when aggregating to each level.

    For every level it compares the magnitude of the *net* aggregate error against the
    *gross* error of the underlying base series:

    - ``gross_abs_error`` : sum of |error| across base rows in each parent (no cancellation).
    - ``net_abs_error``   : |sum of errors| at the aggregate node (after cancellation).
    - ``cancellation_pct``: ``(1 - net/gross) * 100`` — the % of gross error that cancels.
    - ``diversification`` : ``net/gross`` — 0 = perfect cancellation, 1 = errors reinforce.

    High cancellation means base errors are largely **noise** that averages out (the
    aggregate is trustworthy even if base series are noisy). Low cancellation means base
    errors are **correlated / biased** and propagate straight up — the aggregate inherits
    the bias.
    """
    levels = list(levels)
    order = ([TOTAL_LABEL] if include_total else []) + levels
    base_level = levels[-1]
    base = aggregate_to_level(df, levels, base_level, date_col, y_true, y_pred)
    base = base.assign(error=base[y_true] - base[y_pred])

    rows = []
    for lvl in order:
        keys = _agg_keys(levels, lvl)
        if keys:
            grp = base.groupby(keys, dropna=False)["error"]
            net_abs = grp.sum().abs().sum()
        else:
            net_abs = abs(base["error"].sum())
        gross_abs = base["error"].abs().sum()
        div = net_abs / gross_abs if gross_abs != 0 else np.nan
        rows.append({
            "level": lvl,
            "gross_abs_error": float(gross_abs),
            "net_abs_error": float(net_abs),
            "cancellation_pct": float((1 - div) * 100.0) if div == div else np.nan,
            "diversification": float(div) if div == div else np.nan,
        })
    out = pd.DataFrame(rows)
    out["level"] = pd.Categorical(out["level"], categories=order, ordered=True)
    return out.sort_values("level").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def plot_hierarchy_tree(df: pd.DataFrame, levels: Sequence[str], ax=None):
    """Bar chart of node counts per level — the shape/fan-out of the hierarchy."""
    import matplotlib.pyplot as plt

    summary = describe_hierarchy(df, levels)
    if ax is None:
        fig, ax = plt.subplots(figsize=(max(6, len(summary) * 1.2), 4))
    else:
        fig = ax.figure
    ax.bar(summary["level"].astype(str), summary["n_nodes"], color="#4c78a8")
    for x, v in zip(summary["level"].astype(str), summary["n_nodes"]):
        ax.text(x, v, f"{v:,}", ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Number of nodes")
    ax.set_xlabel("Hierarchy level (top → bottom)")
    ax.set_title("Hierarchy shape: nodes per level")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig, ax


def plot_aggregate_actual_vs_forecast(df: pd.DataFrame, levels: Sequence[str], level: str,
                                      node: Optional[str] = None, date_col: str = "ds",
                                      y_true: str = "y", y_pred: str = "y_hat", ax=None):
    """Line chart of aggregated actual vs bottom-up forecast for one node at a level."""
    import matplotlib.pyplot as plt

    agg = aggregate_to_level(df, levels, level, date_col, y_true, y_pred)
    if node is None:
        # Largest node by total forecast, so the default chart is the most material one.
        node = (agg.groupby("node")[y_pred].sum().idxmax())
    sub = agg[agg["node"] == node].sort_values(date_col)

    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 4.5))
    else:
        fig = ax.figure
    ax.plot(sub[date_col], sub[y_true], label="Actual", color="#333", linewidth=1.8)
    ax.plot(sub[date_col], sub[y_pred], label="Forecast (bottom-up)",
            color="#e45756", linewidth=1.8, linestyle="--")
    ax.fill_between(sub[date_col], sub[y_true], sub[y_pred],
                    color="#e45756", alpha=0.12)
    ax.set_title(f"{level} = {node}: aggregated actual vs forecast")
    ax.set_ylabel("Value")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig, ax


def plot_level_contributions(df: pd.DataFrame, levels: Sequence[str], level: str,
                             date_col: str = "ds", y_true: str = "y", y_pred: str = "y_hat",
                             value: str = "y_pred", top_n: int = 8, ax=None):
    """Stacked-area chart of each node's forecast contribution to the aggregate over time.

    The top ``top_n`` nodes are shown individually; the remainder are grouped as "Other".
    This is the time-resolved version of the composition — it shows which parts of the
    business build the aggregate forecast and how their mix shifts.
    """
    import matplotlib.pyplot as plt

    col = y_pred if value == "y_pred" else y_true
    agg = aggregate_to_level(df, levels, level, date_col, y_true, y_pred)
    totals = agg.groupby("node")[col].sum().sort_values(ascending=False)
    keep = list(totals.head(top_n).index)

    agg = agg.copy()
    agg["node_grp"] = np.where(agg["node"].isin(keep), agg["node"], "Other")
    wide = agg.pivot_table(index=date_col, columns="node_grp", values=col,
                           aggfunc="sum", fill_value=0.0)
    ordered = [n for n in keep if n in wide.columns]
    if "Other" in wide.columns:
        ordered.append("Other")
    wide = wide[ordered]

    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 5))
    else:
        fig = ax.figure
    ax.stackplot(wide.index, [wide[c].values for c in wide.columns], labels=wide.columns)
    ax.set_title(f"Forecast contribution to {level} aggregate over time")
    ax.set_ylabel("Value")
    ax.legend(loc="upper left", ncol=2, fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig, ax


def plot_contribution_bars(df: pd.DataFrame, levels: Sequence[str], level: str,
                           date_col: str = "ds", y_true: str = "y", y_pred: str = "y_hat",
                           value: str = "y_pred", top_n: int = 12, ax=None):
    """Horizontal bar chart of each node's total share of the aggregate (Pareto view)."""
    import matplotlib.pyplot as plt

    contrib = level_contributions(df, levels, level, date_col, y_true, y_pred, value=value)
    contrib = contrib.head(top_n).iloc[::-1]

    if ax is None:
        fig, ax = plt.subplots(figsize=(9, max(4, len(contrib) * 0.4)))
    else:
        fig = ax.figure
    ax.barh(contrib["node"].astype(str), contrib["share_pct"], color="#54a24b")
    for y, v in zip(contrib["node"].astype(str), contrib["share_pct"]):
        ax.text(v, y, f" {v:.1f}%", va="center", fontsize=8)
    ax.set_xlabel("Share of aggregate (%)")
    ax.set_title(f"Node contribution to {level} aggregate (top {top_n})")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    return fig, ax


def plot_waterfall(df: pd.DataFrame, levels: Sequence[str], level: str, period,
                   date_col: str = "ds", y_true: str = "y", y_pred: str = "y_hat",
                   value: str = "y_pred", top_n: int = 10, ax=None):
    """Waterfall showing how child nodes build the aggregate for a single ``period``.

    Each bar adds a node's forecast; the final bar is the aggregate. The most direct
    visual answer to *"how does this forecast result in the aggregate?"* for one date.
    """
    import matplotlib.pyplot as plt

    contrib = level_contributions(df, levels, level, date_col, y_true, y_pred,
                                  value=value, period=period)
    head = contrib.head(top_n).copy()
    other_val = contrib["value"].iloc[top_n:].sum()
    labels = list(head["node"].astype(str))
    vals = list(head["value"].values)
    if other_val != 0:
        labels.append("Other")
        vals.append(other_val)
    labels.append(TOTAL_LABEL)
    vals.append(sum(vals))  # aggregate

    if ax is None:
        fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.9), 5))
    else:
        fig = ax.figure

    running = 0.0
    for i, (lab, v) in enumerate(zip(labels, vals)):
        if lab == TOTAL_LABEL:
            ax.bar(lab, v, color="#4c78a8")
            ax.text(i, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=8)
        else:
            ax.bar(lab, v, bottom=running, color="#f58518")
            ax.text(i, running + v, f"{v:,.0f}", ha="center", va="bottom", fontsize=8)
            running += v
    ax.set_ylabel("Forecast value")
    ax.set_title(f"How nodes build the {level} aggregate — {date_col}={period}")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig, ax


def plot_error_by_level(df: pd.DataFrame, levels: Sequence[str],
                        date_col: str = "ds", y_true: str = "y", y_pred: str = "y_hat",
                        metrics: Sequence[str] = ("MAPE", "WMAPE"), ax=None):
    """Line chart of accuracy metrics vs hierarchy level — the propagation curve.

    Falling MAPE/WMAPE from base → Total means errors cancel on aggregation; a flat or
    rising bias (|ME|) means systematic error propagates straight up.
    """
    import matplotlib.pyplot as plt

    tbl = error_by_level(df, levels, date_col, y_true, y_pred)
    if ax is None:
        fig, ax = plt.subplots(figsize=(9, 4.5))
    else:
        fig = ax.figure
    x = tbl["level"].astype(str)
    for m in metrics:
        ax.plot(x, tbl[m], marker="o", label=m)
    ax.set_ylabel("Metric value (% for MAPE/WMAPE)")
    ax.set_xlabel("Hierarchy level (Total → base)")
    ax.set_title("Error propagation across hierarchy levels")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig, ax


def plot_error_propagation(df: pd.DataFrame, levels: Sequence[str], level: str,
                           date_col: str = "ds", y_true: str = "y", y_pred: str = "y_hat",
                           top_n: int = 10, ax=None):
    """Signed-error waterfall: how child errors sum (and cancel) into the aggregate error.

    Positive bars = under-forecast nodes, negative bars = over-forecast nodes; the final
    bar is the *net* aggregate error. Long bars in opposite directions that shrink the
    final bar are cancellation; bars all pointing one way are reinforcing bias.
    """
    import matplotlib.pyplot as plt

    ec = error_contribution(df, levels, level, date_col, y_true, y_pred)
    head = ec.head(top_n).copy()
    other = ec["sum_error"].iloc[top_n:].sum()
    labels = list(head["node"].astype(str))
    vals = list(head["sum_error"].values)
    if other != 0:
        labels.append("Other")
        vals.append(other)
    labels.append("Net aggregate")
    vals.append(sum(vals))

    if ax is None:
        fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.9), 5))
    else:
        fig = ax.figure
    running = 0.0
    for i, (lab, v) in enumerate(zip(labels, vals)):
        color = "#4c78a8" if lab == "Net aggregate" else ("#54a24b" if v >= 0 else "#e45756")
        base = 0.0 if lab == "Net aggregate" else running
        ax.bar(lab, v, bottom=base, color=color)
        if lab != "Net aggregate":
            running += v
    ax.axhline(0, color="#444", linewidth=1)
    ax.set_ylabel("Signed error (actual − forecast)")
    ax.set_title(f"Error propagation into {level} aggregate (green=under, red=over)")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig, ax


def reconciliation_grid(df: pd.DataFrame, levels: Sequence[str],
                        date_col: str = "ds", y_true: str = "y", y_pred: str = "y_hat"):
    """One-page overview: aggregate fit per level (Total + each level's largest node)."""
    import matplotlib.pyplot as plt

    order = [TOTAL_LABEL] + list(levels)
    n = len(order)
    ncols = 2
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 7, nrows * 3.8), squeeze=False)
    for i, lvl in enumerate(order):
        r, c = divmod(i, ncols)
        plot_aggregate_actual_vs_forecast(df, levels, lvl, date_col=date_col,
                                          y_true=y_true, y_pred=y_pred, ax=axes[r][c])
    for j in range(n, nrows * ncols):
        r, c = divmod(j, ncols)
        axes[r][c].set_visible(False)
    fig.suptitle("Reconciliation overview: aggregate fit by level", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    return fig, axes


# ---------------------------------------------------------------------------
# Narratives
# ---------------------------------------------------------------------------

def narrate_hierarchy(df: pd.DataFrame, levels: Sequence[str], target_level: str) -> str:
    """Plain-language description of the hierarchy and the chosen aggregation level."""
    summary = describe_hierarchy(df, levels)
    lines = [
        f"Hierarchy has **{len(levels)} level(s)**: "
        + " → ".join(f"`{l}`" for l in levels) + " (top → bottom).",
        f"Reconciling **bottom-up** to the **{target_level}** level.",
        "",
        "Level shape:",
    ]
    for _, r in summary.iterrows():
        lines.append(
            f"- `{r['level']}`: {int(r['n_nodes']):,} node(s), "
            f"~{r['avg_children_per_parent']:.1f} children per parent."
        )
    return "\n".join(lines)


def narrate_reconciliation(df: pd.DataFrame, levels: Sequence[str], level: str,
                           date_col: str = "ds", y_true: str = "y", y_pred: str = "y_hat",
                           unit: str = "", top_n: int = 5) -> str:
    """Explain how base forecasts compose the aggregate at ``level``.

    Names the nodes that dominate the aggregate forecast (Pareto), which is the natural
    hand-off to ``forecast-explainability``: run ``explain_prediction`` on those dominant
    nodes to see *which feature weights* produced the base forecast that drives the total.
    """
    contrib = level_contributions(df, levels, level, date_col, y_true, y_pred, value="y_pred")
    u = f" {unit}".rstrip()
    total = contrib["value"].sum()
    top = contrib.head(top_n)
    n_for_80 = int((contrib["cum_share_pct"] <= 80).sum()) + 1

    lines = [
        f"Aggregate forecast at **{level}** = **{total:,.0f}{u}** across "
        f"{len(contrib)} node(s).",
        f"The top {len(top)} node(s) make up "
        f"**{top['share_pct'].sum():.0f}%** of the aggregate; "
        f"~**{n_for_80} node(s)** account for 80%.",
        "",
        "Largest contributors to the aggregate forecast:",
    ]
    for _, r in top.iterrows():
        lines.append(f"- **{r['node']}**: {r['value']:,.0f}{u} ({r['share_pct']:.1f}%)")
    lines += [
        "",
        "Next step: run the `forecast-explainability` skill "
        "(`explain_prediction`) on the largest contributor(s) above to see *which "
        "feature weights* drive the base forecast that moves the aggregate.",
    ]
    return "\n".join(lines)


def narrate_error_propagation(df: pd.DataFrame, levels: Sequence[str], level: str,
                              date_col: str = "ds", y_true: str = "y", y_pred: str = "y_hat",
                              unit: str = "", top_n: int = 5) -> str:
    """Explain where the error sits and how it propagates into the aggregate.

    Combines ``error_by_level`` (does error cancel going up?), ``error_cancellation``
    (how much cancels), and ``error_contribution`` (which nodes drive the net miss) into a
    single narrative, and hands off to ``error-analysis`` / ``forecast-explainability``
    for per-point root-causing.
    """
    u = f" {unit}".rstrip()
    lvl_tbl = error_by_level(df, levels, date_col, y_true, y_pred)
    cancel = error_cancellation(df, levels, date_col, y_true, y_pred)
    ec = error_contribution(df, levels, level, date_col, y_true, y_pred, top_n=top_n)

    base = lvl_tbl.iloc[-1]
    total = lvl_tbl.iloc[0]
    cancel_at = cancel[cancel["level"] == level]
    cancel_pct = cancel_at["cancellation_pct"].iloc[0] if not cancel_at.empty else np.nan

    bias_dir = "unbiased"
    if total["ME"] > 0:
        bias_dir = "under-forecasting (actuals exceed forecasts)"
    elif total["ME"] < 0:
        bias_dir = "over-forecasting (forecasts exceed actuals)"

    lines = [
        f"Base-level accuracy: MAPE **{base['MAPE']:.1f}%**, WMAPE "
        f"**{base['WMAPE']:.1f}%**, ME **{base['ME']:,.0f}{u}**.",
        f"Aggregate ({total['level']}) accuracy: MAPE **{total['MAPE']:.1f}%**, "
        f"WMAPE **{total['WMAPE']:.1f}%**, ME **{total['ME']:,.0f}{u}** → the "
        f"aggregate is **{bias_dir}**.",
    ]
    if cancel_pct == cancel_pct:
        if cancel_pct >= 50:
            behaviour = (f"**{cancel_pct:.0f}% of gross base error cancels** at the "
                         f"{level} level — base misses are largely noise that averages "
                         f"out, so the aggregate is more reliable than the base series.")
        else:
            behaviour = (f"only **{cancel_pct:.0f}% of gross base error cancels** at the "
                         f"{level} level — base errors are correlated/biased and "
                         f"**propagate** into the aggregate.")
        lines += ["", behaviour]

    lines += ["", f"Nodes driving the net error at **{level}** (signed):"]
    for _, r in ec.iterrows():
        direction = "under" if r["sum_error"] > 0 else "over"
        lines.append(
            f"- **{r['node']}**: {r['sum_error']:,.0f}{u} ({direction}-forecast), "
            f"{r['share_of_abs_pct']:.1f}% of gross error."
        )
    lines += [
        "",
        "Next steps: (1) run the `error-analysis` skill (`compute_errors` / "
        "`worst_buckets`) on the driver node(s) to see *when* they miss; "
        "(2) run `forecast-explainability` (`explain_prediction`) on those points to see "
        "*which feature weights* caused the miss that propagated into the aggregate.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_cols(df: pd.DataFrame, cols: Sequence[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"Columns not found in DataFrame: {missing}. "
                       f"Available: {list(df.columns)}")
