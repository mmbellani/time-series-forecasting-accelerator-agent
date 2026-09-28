"""Forecast error-analysis utilities.

Evaluate time-series forecast accuracy and decompose the error by calendar
variables. Built for the Time Series Forecasting Accelerator pipeline
(LightGBM + mlforecast, notebook 06), whose ``<scenario>_forecasts`` output holds
``unique_id``, ``ds`` (date), ``y`` (actual), and one or more ``y_hat_*`` prediction
columns. Works with any tidy actuals-vs-predictions frame.

Run this skill **after** the ``forecast-explainability`` skill: understanding *why*
the model produced a value (feature weights / SHAP) is what turns a raw error bucket
into an actionable diagnosis of *why the forecast was wrong*.

Error convention
----------------
This module uses the forecasting-standard residual::

    error = y_true - y_pred      # actual minus forecast (Hyndman convention)

- ``error > 0``  → **under-forecast** (actual exceeded the forecast)
- ``error < 0``  → **over-forecast** (forecast exceeded the actual)
- ``ME`` (Mean Error / bias) is the mean of ``error``; a value near 0 means the
  forecast is unbiased.

Metrics
-------
- ``MAE``  : mean absolute error            = mean(|error|)
- ``MAPE`` : mean absolute percentage error = mean(|error| / |y_true|) * 100
- ``ME``   : mean error (bias)              = mean(error)
- ``RMSE`` : root mean squared error        = sqrt(mean(error^2))

Public API
----------
- ``add_calendar_features``  : derive year / quarter / month / week / dow columns from a date.
- ``compute_errors``         : per-row error frame (error, abs_error, ape, squared_error + calendar).
- ``metric_summary``         : overall MAE / MAPE / ME / RMSE (+ WMAPE, sMAPE) for one prediction column.
- ``metrics_by_calendar``    : the four metrics decomposed by a calendar variable.
- ``error_boxplot``          : box-plot of the per-row error distribution grouped by a calendar variable.
- ``boxplot_grid``           : a grid of box-plots (one metric across several calendar variables).
- ``worst_buckets``          : rank calendar buckets by a metric to target root-cause analysis.
- ``narrate_errors``         : plain-language summary of accuracy, bias, and error hot-spots.

``matplotlib`` is only required for the plotting helpers (``error_boxplot`` / ``boxplot_grid``).
The metric functions have no plotting dependency.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Calendar features
# ---------------------------------------------------------------------------

# Default calendar variables to decompose by. Ordered from coarse to fine.
DEFAULT_CALENDAR_VARS: List[str] = ["year", "quarter", "month", "week", "dayofweek"]

# Human-readable month / weekday labels for nicer plots and narratives.
_MONTH_LABELS = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}
_DOW_LABELS = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}


def add_calendar_features(df: pd.DataFrame, date_col: str = "ds") -> pd.DataFrame:
    """Return a copy of ``df`` with calendar columns derived from ``date_col``.

    Adds: ``year``, ``quarter``, ``month``, ``week`` (ISO week), ``day``,
    ``dayofweek`` (0=Mon), ``is_month_start``, ``is_month_end``. Existing columns
    with these names are overwritten so the decomposition is always consistent.
    """
    out = df.copy()
    ts = pd.to_datetime(out[date_col])
    out["year"] = ts.dt.year
    out["quarter"] = ts.dt.quarter
    out["month"] = ts.dt.month
    out["week"] = ts.dt.isocalendar().week.astype(int)
    out["day"] = ts.dt.day
    out["dayofweek"] = ts.dt.dayofweek
    out["is_month_start"] = ts.dt.is_month_start
    out["is_month_end"] = ts.dt.is_month_end
    return out


def _label_bucket(var: str, value):
    """Map a raw calendar bucket value to a friendly label where helpful."""
    if pd.isna(value):
        return value
    if var == "month":
        return _MONTH_LABELS.get(int(value), value)
    if var == "dayofweek":
        return _DOW_LABELS.get(int(value), value)
    if var == "quarter":
        return f"Q{int(value)}"
    if var in {"year", "week", "day"}:
        # Render whole-number buckets without a trailing ".0".
        return int(value)
    return value


# ---------------------------------------------------------------------------
# Per-row error computation
# ---------------------------------------------------------------------------

# Which per-row column each headline metric summarizes / plots as a distribution.
_METRIC_ROWCOL: Dict[str, str] = {
    "ME": "error",          # signed error -> bias distribution
    "MAE": "abs_error",     # absolute error distribution
    "MAPE": "ape",          # absolute percentage error distribution (already in %)
    "RMSE": "squared_error",  # squared error distribution (skewed; see error_boxplot note)
}


def compute_errors(df: pd.DataFrame, y_true: str = "y", y_pred: str = "y_hat",
                   date_col: str = "ds", id_col: Optional[str] = "unique_id",
                   calendar_vars: Optional[Sequence[str]] = None,
                   drop_zero_actual_ape: bool = True) -> pd.DataFrame:
    """Build a tidy per-row error frame with calendar decomposition columns.

    Parameters
    ----------
    df
        Frame containing actuals and predictions (e.g. ``<scenario>_forecasts``
        joined to actuals).
    y_true, y_pred
        Column names for the actual and predicted values.
    date_col
        Date column used to derive calendar variables.
    id_col
        Optional series identifier to carry through (kept if present).
    calendar_vars
        Calendar columns to ensure exist. Defaults to :data:`DEFAULT_CALENDAR_VARS`.
    drop_zero_actual_ape
        When ``True`` (default), ``ape`` is ``NaN`` where ``y_true == 0`` (MAPE is
        undefined there). The absolute/signed/squared errors are still computed.

    Returns
    -------
    pandas.DataFrame
        Columns: [id_col], date_col, y_true, y_pred, ``error``, ``abs_error``,
        ``squared_error``, ``ape`` (percent), plus calendar variables.
    """
    calendar_vars = list(calendar_vars) if calendar_vars else list(DEFAULT_CALENDAR_VARS)

    work = add_calendar_features(df, date_col)

    actual = work[y_true].astype(float)
    pred = work[y_pred].astype(float)

    error = actual - pred                      # Hyndman residual: actual - forecast
    abs_error = error.abs()
    squared_error = error ** 2

    denom = actual.abs()
    with np.errstate(divide="ignore", invalid="ignore"):
        ape = (abs_error / denom) * 100.0
    if drop_zero_actual_ape:
        ape = ape.where(actual != 0, other=np.nan)
    ape = ape.replace([np.inf, -np.inf], np.nan)

    keep_cols: List[str] = []
    if id_col and id_col in work.columns:
        keep_cols.append(id_col)
    keep_cols += [date_col, y_true, y_pred]

    out = work[keep_cols].copy()
    out["error"] = error.values
    out["abs_error"] = abs_error.values
    out["squared_error"] = squared_error.values
    out["ape"] = ape.values
    for var in calendar_vars:
        if var in work.columns:
            out[var] = work[var].values
    return out


# ---------------------------------------------------------------------------
# Scalar metric summaries
# ---------------------------------------------------------------------------

def _metrics_from_arrays(actual: np.ndarray, pred: np.ndarray) -> Dict[str, float]:
    actual = np.asarray(actual, dtype=float)
    pred = np.asarray(pred, dtype=float)
    error = actual - pred
    abs_error = np.abs(error)

    n = len(error)
    if n == 0:
        return {"n": 0, "ME": np.nan, "MAE": np.nan, "RMSE": np.nan,
                "MAPE": np.nan, "sMAPE": np.nan, "WMAPE": np.nan}

    valid = actual != 0
    ape = np.where(valid, abs_error / np.abs(actual), np.nan)

    smape_denom = (np.abs(actual) + np.abs(pred)) / 2.0
    smape = np.where(smape_denom != 0, abs_error / smape_denom, np.nan)

    total_actual = np.abs(actual).sum()
    wmape = abs_error.sum() / total_actual if total_actual != 0 else np.nan

    return {
        "n": int(n),
        "ME": float(np.mean(error)),
        "MAE": float(np.mean(abs_error)),
        "RMSE": float(np.sqrt(np.mean(error ** 2))),
        "MAPE": float(np.nanmean(ape) * 100.0),
        "sMAPE": float(np.nanmean(smape) * 100.0),
        "WMAPE": float(wmape * 100.0) if wmape == wmape else np.nan,
    }


def metric_summary(df: pd.DataFrame, y_true: str = "y", y_pred: str = "y_hat") -> pd.Series:
    """Overall accuracy metrics for one prediction column.

    Returns a Series with ``n``, ``ME``, ``MAE``, ``RMSE``, ``MAPE`` (%),
    ``sMAPE`` (%), and ``WMAPE`` (%).
    """
    m = _metrics_from_arrays(df[y_true].values, df[y_pred].values)
    return pd.Series(m)


def compare_models(df: pd.DataFrame, y_true: str = "y",
                   pred_cols: Optional[Sequence[str]] = None,
                   sort_by: str = "MAE") -> pd.DataFrame:
    """Compute the metric table for several prediction columns and rank them.

    When ``pred_cols`` is ``None``, every column starting with ``y_hat_`` is used
    (matching the notebook-06 naming convention).
    """
    if pred_cols is None:
        pred_cols = [c for c in df.columns if c.startswith("y_hat_")]
    rows = []
    for col in pred_cols:
        m = _metrics_from_arrays(df[y_true].values, df[col].values)
        m = {"model": col, **m}
        rows.append(m)
    out = pd.DataFrame(rows)
    if sort_by in out.columns:
        out = out.sort_values(sort_by).reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------
# Calendar decomposition
# ---------------------------------------------------------------------------

def metrics_by_calendar(errors_df: pd.DataFrame, by: str,
                        y_true: str = "y", y_pred: str = "y_hat",
                        add_labels: bool = True) -> pd.DataFrame:
    """Decompose MAE / MAPE / ME / RMSE across a single calendar variable.

    Parameters
    ----------
    errors_df
        Output of :func:`compute_errors` (must already contain ``error``,
        ``abs_error``, ``squared_error``, ``ape`` and the ``by`` column).
    by
        Calendar column to group by (e.g. ``"month"``, ``"quarter"``, ``"week"``).

    Returns
    -------
    pandas.DataFrame
        One row per bucket with ``n``, ``ME``, ``MAE``, ``RMSE``, ``MAPE`` (%),
        sorted by the natural bucket order.
    """
    if by not in errors_df.columns:
        raise KeyError(f"Calendar variable '{by}' not found in errors_df columns.")

    grouped = errors_df.groupby(by, dropna=False)
    summary = pd.DataFrame({
        "n": grouped["error"].size(),
        "ME": grouped["error"].mean(),
        "MAE": grouped["abs_error"].mean(),
        "RMSE": grouped["squared_error"].mean().pow(0.5),
        "MAPE": grouped["ape"].mean(),  # ape already in percent
    }).reset_index()

    summary = summary.sort_values(by).reset_index(drop=True)
    if add_labels:
        summary.insert(1, "bucket", summary[by].map(lambda v: _label_bucket(by, v)))
    return summary


def worst_buckets(errors_df: pd.DataFrame, by: str, metric: str = "MAE",
                  top_n: int = 5, y_true: str = "y", y_pred: str = "y_hat") -> pd.DataFrame:
    """Return the ``top_n`` calendar buckets with the largest error for ``metric``.

    For ``ME`` the ranking is by absolute bias (largest |ME| first); for the other
    metrics larger is worse. Use this to pick the buckets to hand back to the
    ``forecast-explainability`` skill for root-cause analysis.
    """
    if metric not in {"MAE", "MAPE", "ME", "RMSE"}:
        raise ValueError("metric must be one of MAE, MAPE, ME, RMSE.")
    table = metrics_by_calendar(errors_df, by, y_true, y_pred)
    if metric == "ME":
        table = table.reindex(table["ME"].abs().sort_values(ascending=False).index)
    else:
        table = table.sort_values(metric, ascending=False)
    return table.head(top_n).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Box-plots
# ---------------------------------------------------------------------------

def error_boxplot(errors_df: pd.DataFrame, by: str, metric: str = "MAE",
                  ax=None, showfliers: bool = True, title: Optional[str] = None):
    """Box-plot of the per-row error distribution grouped by a calendar variable.

    Each box shows the spread of the per-observation error component that the
    headline ``metric`` summarizes:

    ======  =========================  ==============================================
    metric  per-row column plotted     what the distribution tells you
    ======  =========================  ==============================================
    MAE     ``abs_error``              magnitude of misses per bucket
    MAPE    ``ape`` (percent)          relative miss size per bucket
    ME      ``error`` (signed)         bias direction & spread (0 line = unbiased)
    RMSE    ``squared_error``          variance of misses (heavy-tailed; see note)
    ======  =========================  ==============================================

    Notes
    -----
    - For ``ME`` a horizontal reference line at 0 is drawn: boxes sitting above 0
      indicate systematic **under-forecasting**, below 0 **over-forecasting**.
    - ``RMSE`` maps to the squared-error distribution, which is strongly
      right-skewed; the box is still useful for *comparing* buckets but is not a
      symmetric spread. Prefer ``MAE``'s box for reading absolute magnitude.

    Returns
    -------
    (fig, ax)
        The matplotlib figure and axis (create a new figure when ``ax`` is None).
    """
    import matplotlib.pyplot as plt

    if metric not in _METRIC_ROWCOL:
        raise ValueError("metric must be one of MAE, MAPE, ME, RMSE.")
    value_col = _METRIC_ROWCOL[metric]
    if by not in errors_df.columns:
        raise KeyError(f"Calendar variable '{by}' not found in errors_df columns.")

    data = errors_df[[by, value_col]].dropna(subset=[value_col])
    buckets = sorted(data[by].dropna().unique())
    groups = [data.loc[data[by] == b, value_col].values for b in buckets]
    labels = [str(_label_bucket(by, b)) for b in buckets]

    if ax is None:
        fig, ax = plt.subplots(figsize=(max(8, len(buckets) * 0.7), 5))
    else:
        fig = ax.figure

    # `tick_labels` (matplotlib >= 3.9) replaced the older `labels` kwarg; set the
    # tick labels explicitly afterwards so the helper works across versions.
    ax.boxplot(groups, showfliers=showfliers, patch_artist=True,
               boxprops=dict(facecolor="#cfe3f5", edgecolor="#2b6cb0"),
               medianprops=dict(color="#c53030", linewidth=1.5),
               flierprops=dict(marker="o", markersize=3, alpha=0.4))
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, rotation=0)

    if metric == "ME":
        ax.axhline(0.0, color="#444", linestyle="--", linewidth=1)

    ylabel = {"MAE": "Absolute error", "MAPE": "APE (%)",
              "ME": "Error (actual − forecast)", "RMSE": "Squared error"}[metric]
    ax.set_ylabel(ylabel)
    ax.set_xlabel(by)
    ax.set_title(title or f"{metric} error distribution by {by}")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig, ax


def boxplot_grid(errors_df: pd.DataFrame, calendar_vars: Optional[Sequence[str]] = None,
                 metric: str = "MAE", ncols: int = 2, showfliers: bool = False):
    """Grid of :func:`error_boxplot` panels — one calendar variable per panel.

    Useful for a single at-a-glance page: "where does the error concentrate?".
    Returns ``(fig, axes)``.
    """
    import matplotlib.pyplot as plt

    calendar_vars = list(calendar_vars) if calendar_vars else [
        v for v in DEFAULT_CALENDAR_VARS if v in errors_df.columns
    ]
    n = len(calendar_vars)
    if n == 0:
        raise ValueError("No calendar variables available in errors_df.")
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 7, nrows * 4.2), squeeze=False)

    for i, var in enumerate(calendar_vars):
        r, c = divmod(i, ncols)
        error_boxplot(errors_df, var, metric=metric, ax=axes[r][c], showfliers=showfliers)
    # Hide any unused panels
    for j in range(n, nrows * ncols):
        r, c = divmod(j, ncols)
        axes[r][c].set_visible(False)

    fig.suptitle(f"{metric} error distribution by calendar variable", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    return fig, axes


# ---------------------------------------------------------------------------
# Narrative
# ---------------------------------------------------------------------------

def narrate_errors(errors_df: pd.DataFrame, calendar_vars: Optional[Sequence[str]] = None,
                   y_true: str = "y", y_pred: str = "y_hat", unit: str = "") -> str:
    """Produce a plain-language summary of accuracy, bias, and error hot-spots.

    Reports overall MAE / MAPE / ME / RMSE, states the bias direction, and names
    the worst calendar bucket for each variable — the natural hand-off to the
    ``forecast-explainability`` skill for a per-point root-cause explanation.
    """
    overall = _metrics_from_arrays(errors_df[y_true].values, errors_df[y_pred].values)
    u = f" {unit}".rstrip()

    def fmt(v: float) -> str:
        return f"{v:,.2f}{u}"

    bias_dir = "unbiased"
    if overall["ME"] > 0:
        bias_dir = "under-forecasting (actuals tend to exceed forecasts)"
    elif overall["ME"] < 0:
        bias_dir = "over-forecasting (forecasts tend to exceed actuals)"

    lines: List[str] = [
        f"Overall accuracy on {overall['n']:,} points: "
        f"MAE **{fmt(overall['MAE'])}**, RMSE **{fmt(overall['RMSE'])}**, "
        f"MAPE **{overall['MAPE']:.1f}%**.",
        f"Bias: ME **{fmt(overall['ME'])}** → the model is **{bias_dir}**.",
    ]

    calendar_vars = list(calendar_vars) if calendar_vars else [
        v for v in DEFAULT_CALENDAR_VARS if v in errors_df.columns
    ]
    if calendar_vars:
        lines.append("")
        lines.append("Error hot-spots (worst bucket per calendar variable, by MAE):")
        for var in calendar_vars:
            try:
                w = worst_buckets(errors_df, var, metric="MAE", top_n=1,
                                  y_true=y_true, y_pred=y_pred)
            except KeyError:
                continue
            if w.empty:
                continue
            # Read scalars column-wise: w.iloc[0] would unify the row to one dtype
            # and turn integer buckets (e.g. year) into floats like 2023.0.
            label = w["bucket"].iloc[0] if "bucket" in w.columns else w[var].iloc[0]
            lines.append(
                f"- **{var} = {label}**: MAE {fmt(w['MAE'].iloc[0])}, "
                f"MAPE {w['MAPE'].iloc[0]:.1f}%, ME {fmt(w['ME'].iloc[0])} "
                f"(n={int(w['n'].iloc[0])})"
            )
        lines.append("")
        lines.append(
            "Next step: take the worst bucket(s) above and run the "
            "`forecast-explainability` skill (`explain_prediction`) on individual "
            "points inside them to see *which feature weights* produced the miss."
        )

    return "\n".join(lines)
