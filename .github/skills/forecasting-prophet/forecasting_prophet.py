"""Prophet forecasting utilities (additive trend + seasonality model).

Generate forecasts for time series with Facebook/Meta's **Prophet** — a decomposable
additive model (trend + seasonality + holidays) that is robust to missing data and
trend shifts — and benchmark it against the pipeline's LightGBM baseline.

Built for the Time Series Forecasting Accelerator pipeline, where the panel has
``unique_id`` (series id), ``ds`` (date), ``y`` (actual value) and a
``profile_cluster`` grouping column (produced by notebooks 03/04). The LightGBM
baseline lives in ``<scenario>_forecasts`` as one or more ``y_hat_*`` columns
(notebook 06).

Two run scopes (both required by design)
----------------------------------------
1. **Global**  -- fit Prophet across the *entire* panel (one model per series) in a
   single ``forecast_global`` run. Selection and scoring are pooled across all
   series, yielding one winning Prophet configuration for the whole dataset.
2. **By profile-cluster** -- subset the panel by ``profile_cluster`` and run
   ``forecast_by_cluster`` per cluster, so the *best* Prophet configuration can be
   chosen per cluster.

Prophet is an **inherently local** model: it fits one model per series. "Global vs
cluster" therefore changes *scoring and model selection* (and, optionally, which
per-cluster hyperparameters are used), not whether series are pooled into a shared
fit.

Models
------
Each "model" is a named Prophet configuration (a set of constructor kwargs):

- ``Prophet``            : default additive Prophet (auto seasonality).
- ``Prophet_Mult``       : multiplicative seasonality (good for growing series).
- ``Prophet_Flexible``   : higher ``changepoint_prior_scale`` (more trend flexibility).
- ``Prophet_Smooth``     : lower ``changepoint_prior_scale`` (stiffer trend).
- ``Prophet_Yearly``     : yearly seasonality forced on (weekly/daily off).

Metrics
-------
Headline metrics are scale-free / robust so they compare fairly against LightGBM
and stay well-defined on series with zero periods:

- ``MAE``   : mean absolute error            = mean(|y - yhat|)
- ``RMSE``  : root mean squared error        = sqrt(mean((y - yhat)^2))
- ``WMAPE`` : weighted MAPE                   = sum(|y - yhat|) / sum(|y|) * 100
- ``ME``    : mean error (bias)              = mean(y - yhat)

Error convention (Hyndman): ``error = y - yhat`` (actual minus forecast); a
positive ``ME`` means under-forecasting.

Public API
----------
- ``build_models``          : construct the list of named Prophet configurations.
- ``forecast_global``       : rolling-origin backtest of Prophet on the whole panel.
- ``forecast_by_cluster``   : rolling-origin backtest of Prophet per ``profile_cluster``.
- ``predict_future``        : fit on all history and produce future-horizon forecasts.
- ``evaluate_forecasts``    : MAE / RMSE / WMAPE / ME per model column.
- ``select_best``           : pick the winning model overall or per group.
- ``compare_to_baseline``   : join Prophet forecasts to LightGBM ``y_hat_*`` and rank.
- ``narrate_comparison``    : plain-language summary of the benchmark.

``prophet`` is required for the forecasting functions. The evaluation and narration
helpers work on any tidy actuals-vs-predictions frame and have no ``prophet``
dependency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Quiet Prophet / cmdstanpy — they are extremely chatty by default
# ---------------------------------------------------------------------------

for _noisy in ("prophet", "cmdstanpy", "prophet.forecaster"):
    logging.getLogger(_noisy).setLevel(logging.CRITICAL)


# ---------------------------------------------------------------------------
# Model catalogue
# ---------------------------------------------------------------------------


@dataclass
class ProphetModel:
    """A named Prophet configuration (constructor kwargs)."""

    name: str
    kwargs: Dict = field(default_factory=dict)


# Default set of Prophet configurations to evaluate.
DEFAULT_PROPHET_MODELS: Dict[str, Dict] = {
    "Prophet": {},
    "Prophet_Mult": {"seasonality_mode": "multiplicative"},
    "Prophet_Flexible": {"changepoint_prior_scale": 0.5},
    "Prophet_Smooth": {"changepoint_prior_scale": 0.01},
    "Prophet_Yearly": {
        "yearly_seasonality": True,
        "weekly_seasonality": False,
        "daily_seasonality": False,
    },
}


def build_models(
    include: Optional[Sequence[str]] = None,
    extra: Optional[Dict[str, Dict]] = None,
) -> List[ProphetModel]:
    """Construct the named Prophet configurations for the benchmark.

    Parameters
    ----------
    include
        Names of configurations to build (subset of ``DEFAULT_PROPHET_MODELS``).
        Defaults to all default configurations.
    extra
        Optional mapping of ``{name: kwargs}`` for additional custom Prophet
        configurations (e.g. with holidays or extra seasonalities).

    Returns
    -------
    list of ProphetModel
        Ready to pass to ``forecast_global`` / ``forecast_by_cluster``.
    """
    catalogue = dict(DEFAULT_PROPHET_MODELS)
    if extra:
        catalogue.update(extra)

    names = list(include) if include is not None else list(DEFAULT_PROPHET_MODELS)

    unknown = [n for n in names if n not in catalogue]
    if unknown:
        raise ValueError(
            f"Unknown model name(s): {unknown}. Available: {sorted(catalogue)}"
        )
    return [ProphetModel(name=n, kwargs=dict(catalogue[n])) for n in names]


def model_names(models: Sequence[ProphetModel]) -> List[str]:
    """Return the output-column names for a list of Prophet models."""
    return [m.name for m in models]


# ---------------------------------------------------------------------------
# Panel helpers
# ---------------------------------------------------------------------------

_RESERVED = {"unique_id", "ds", "cutoff", "y", "scope", "profile_cluster"}


def _require_panel(
    df: pd.DataFrame, id_col: str, date_col: str, target: str
) -> pd.DataFrame:
    """Return a clean panel with canonical ``unique_id`` / ``ds`` / ``y`` columns."""
    missing = [c for c in (id_col, date_col, target) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required column(s): {missing}")
    panel = df[[id_col, date_col, target]].rename(
        columns={id_col: "unique_id", date_col: "ds", target: "y"}
    ).copy()
    panel["ds"] = pd.to_datetime(panel["ds"])
    return panel.sort_values(["unique_id", "ds"]).reset_index(drop=True)


def _rolling_cutoff_indices(n_obs: int, h: int, n_windows: int, step_size: int) -> List[int]:
    """Return train-end indices (exclusive) for each rolling-origin window.

    Windows are anchored at the end of the series: the last window's test set is the
    final ``h`` observations, and earlier windows step back by ``step_size``.
    """
    indices: List[int] = []
    for i in range(n_windows):
        train_end = n_obs - h - (n_windows - 1 - i) * step_size
        if train_end <= 1:  # need at least 2 points to fit Prophet
            continue
        indices.append(train_end)
    return indices


def _fit_predict_prophet(
    train: pd.DataFrame, future_ds: pd.Series, kwargs: Dict
) -> np.ndarray:
    """Fit a single Prophet model on ``train`` and predict for ``future_ds`` dates."""
    from prophet import Prophet

    model = Prophet(**kwargs)
    model.fit(train[["ds", "y"]])
    future = pd.DataFrame({"ds": pd.to_datetime(future_ds.values)})
    fcst = model.predict(future)
    return fcst["yhat"].to_numpy(dtype=float)


# ---------------------------------------------------------------------------
# Forecasting — global scope (entire panel)
# ---------------------------------------------------------------------------


def forecast_global(
    df: pd.DataFrame,
    h: int,
    freq: str = "MS",
    models: Optional[Sequence[ProphetModel]] = None,
    n_windows: int = 3,
    step_size: Optional[int] = None,
    id_col: str = "unique_id",
    date_col: str = "ds",
    target: str = "y",
) -> pd.DataFrame:
    """Rolling-origin backtest of Prophet models on the ENTIRE panel.

    For every series and every rolling window, each Prophet configuration is fitted
    on the history up to the cutoff and predicts the next ``h`` steps. Every
    prediction is therefore out-of-sample and carries the matching actual ``y`` and
    ``cutoff`` — making the result directly comparable to the LightGBM baseline on
    the same windows.

    Parameters
    ----------
    df
        Panel with id / date / target columns (extra columns are ignored).
    h
        Forecast horizon (number of periods per window).
    freq
        Pandas offset alias matching the data granularity (e.g. ``"MS"`` monthly).
        Retained for API symmetry / documentation; predictions use the actual
        observed test dates.
    models
        List of ``ProphetModel``; defaults to ``build_models()``.
    n_windows, step_size
        Rolling-origin backtest configuration. ``step_size`` defaults to ``h``.

    Returns
    -------
    pandas.DataFrame
        Cross-validation frame with columns ``unique_id``, ``ds``, ``cutoff``,
        ``y`` and one column per model. ``scope`` is set to ``"global"``.
    """
    panel = _require_panel(df, id_col, date_col, target)
    models = list(models) if models is not None else build_models()
    step_size = step_size if step_size is not None else h
    cols = model_names(models)

    rows: List[pd.DataFrame] = []
    for uid, series in panel.groupby("unique_id"):
        series = series.reset_index(drop=True)
        n_obs = len(series)
        for train_end in _rolling_cutoff_indices(n_obs, h, n_windows, step_size):
            train = series.iloc[:train_end]
            test = series.iloc[train_end : train_end + h]
            if test.empty:
                continue
            cutoff = train["ds"].iloc[-1]
            window = pd.DataFrame(
                {
                    "unique_id": uid,
                    "ds": test["ds"].to_numpy(),
                    "cutoff": cutoff,
                    "y": test["y"].to_numpy(dtype=float),
                }
            )
            for model in models:
                try:
                    yhat = _fit_predict_prophet(train, test["ds"], model.kwargs)
                except Exception:  # pragma: no cover - a bad fit shouldn't kill the run
                    yhat = np.full(len(test), np.nan)
                window[model.name] = yhat
            rows.append(window)

    if not rows:
        raise ValueError(
            "No backtest windows were produced. Check h / n_windows against series length."
        )

    cv = pd.concat(rows, ignore_index=True)
    cv["scope"] = "global"
    return cv[["unique_id", "ds", "cutoff", "y", *cols, "scope"]]


# ---------------------------------------------------------------------------
# Forecasting — by profile_cluster
# ---------------------------------------------------------------------------


def forecast_by_cluster(
    df: pd.DataFrame,
    h: int,
    group_col: str = "profile_cluster",
    freq: str = "MS",
    models: Optional[Sequence[ProphetModel]] = None,
    n_windows: int = 3,
    step_size: Optional[int] = None,
    id_col: str = "unique_id",
    date_col: str = "ds",
    target: str = "y",
) -> pd.DataFrame:
    """Rolling-origin backtest of Prophet models PER ``profile_cluster``.

    Runs one ``forecast_global`` backtest per cluster so the best Prophet
    configuration can be selected per cluster (see ``select_best``). The combined
    result carries the ``profile_cluster`` label alongside each row.

    Returns
    -------
    pandas.DataFrame
        Cross-validation frame with ``unique_id``, ``ds``, ``cutoff``, ``y``, one
        column per model, plus ``profile_cluster`` and ``scope`` (``"cluster:<id>"``).
    """
    if group_col not in df.columns:
        raise KeyError(
            f"Grouping column '{group_col}' not found. Available: {list(df.columns)}"
        )

    models = list(models) if models is not None else build_models()
    step_size = step_size if step_size is not None else h

    id_to_cluster = (
        df[[id_col, group_col]].drop_duplicates().set_index(id_col)[group_col].to_dict()
    )

    frames: List[pd.DataFrame] = []
    for cluster_id, group_df in df.groupby(group_col):
        if group_df[id_col].nunique() == 0:
            continue
        cv = forecast_global(
            group_df,
            h=h,
            freq=freq,
            models=models,
            n_windows=n_windows,
            step_size=step_size,
            id_col=id_col,
            date_col=date_col,
            target=target,
        )
        cv["profile_cluster"] = cluster_id
        cv["scope"] = f"cluster:{cluster_id}"
        frames.append(cv)

    if not frames:
        raise ValueError("No clusters produced any forecasts.")

    out = pd.concat(frames, ignore_index=True)
    out["profile_cluster"] = out["profile_cluster"].fillna(
        out["unique_id"].map(id_to_cluster)
    )
    return out


def predict_future(
    df: pd.DataFrame,
    h: int,
    freq: str = "MS",
    models: Optional[Sequence[ProphetModel]] = None,
    id_col: str = "unique_id",
    date_col: str = "ds",
    target: str = "y",
) -> pd.DataFrame:
    """Fit Prophet on all history and produce genuine future-horizon forecasts.

    Use this once a model has been selected; unlike the ``forecast_*`` backtests
    this returns forward-looking predictions with no matching actuals.

    Returns
    -------
    pandas.DataFrame
        Columns ``unique_id``, ``ds`` and one column per model with the point
        forecast for each of the next ``h`` periods.
    """
    from prophet import Prophet

    panel = _require_panel(df, id_col, date_col, target)
    models = list(models) if models is not None else build_models()

    frames: List[pd.DataFrame] = []
    for uid, series in panel.groupby("unique_id"):
        series = series.sort_values("ds").reset_index(drop=True)
        preds = {"unique_id": uid}
        future_ds = None
        for model in models:
            m = Prophet(**model.kwargs)
            m.fit(series[["ds", "y"]])
            future = m.make_future_dataframe(periods=h, freq=freq, include_history=False)
            fcst = m.predict(future)
            future_ds = fcst["ds"].to_numpy()
            preds[model.name] = fcst["yhat"].to_numpy(dtype=float)
        frame = pd.DataFrame({"unique_id": uid, "ds": future_ds})
        for model in models:
            frame[model.name] = preds[model.name]
        frames.append(frame)

    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def _mae(y: np.ndarray, yhat: np.ndarray) -> float:
    return float(np.mean(np.abs(y - yhat)))


def _rmse(y: np.ndarray, yhat: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y - yhat) ** 2)))


def _wmape(y: np.ndarray, yhat: np.ndarray) -> float:
    denom = np.sum(np.abs(y))
    if denom == 0:
        return float("nan")
    return float(np.sum(np.abs(y - yhat)) / denom * 100.0)


def _bias(y: np.ndarray, yhat: np.ndarray) -> float:
    return float(np.mean(y - yhat))


def evaluate_forecasts(
    cv_df: pd.DataFrame,
    model_cols: Optional[Sequence[str]] = None,
    y_true: str = "y",
    group_by: Optional[str] = None,
) -> pd.DataFrame:
    """Score each model column with MAE / RMSE / WMAPE / ME.

    Parameters
    ----------
    cv_df
        Output of ``forecast_global`` / ``forecast_by_cluster`` (or any frame with
        ``y`` and one column per model).
    model_cols
        Which prediction columns to score. Defaults to every non-reserved numeric
        column (i.e. all model outputs).
    y_true
        Actuals column name.
    group_by
        Optional column to break the metrics down by (e.g. ``"profile_cluster"``).

    Returns
    -------
    pandas.DataFrame
        Tidy metrics with columns ``model``, ``MAE``, ``RMSE``, ``WMAPE``, ``ME``,
        ``n`` (and the group column when ``group_by`` is set).
    """
    reserved = set(_RESERVED)
    if model_cols is None:
        model_cols = [
            c
            for c in cv_df.columns
            if c not in reserved and pd.api.types.is_numeric_dtype(cv_df[c])
        ]
    if not model_cols:
        raise ValueError("No model prediction columns found to evaluate.")

    def _score(frame: pd.DataFrame) -> List[dict]:
        rows = []
        y = frame[y_true].to_numpy(dtype=float)
        for col in model_cols:
            yhat = frame[col].to_numpy(dtype=float)
            mask = ~(np.isnan(y) | np.isnan(yhat))
            yv, yhv = y[mask], yhat[mask]
            if yv.size == 0:
                continue
            rows.append(
                {
                    "model": col,
                    "MAE": _mae(yv, yhv),
                    "RMSE": _rmse(yv, yhv),
                    "WMAPE": _wmape(yv, yhv),
                    "ME": _bias(yv, yhv),
                    "n": int(yv.size),
                }
            )
        return rows

    if group_by is not None:
        if group_by not in cv_df.columns:
            raise KeyError(f"group_by column '{group_by}' not found.")
        out_rows = []
        for gval, gframe in cv_df.groupby(group_by):
            for r in _score(gframe):
                r[group_by] = gval
                out_rows.append(r)
        cols = [group_by, "model", "MAE", "RMSE", "WMAPE", "ME", "n"]
        return (
            pd.DataFrame(out_rows)[cols]
            .sort_values([group_by, "MAE"])
            .reset_index(drop=True)
        )

    return pd.DataFrame(_score(cv_df)).sort_values("MAE").reset_index(drop=True)


def select_best(
    metrics: pd.DataFrame,
    metric: str = "MAE",
    group_by: Optional[str] = None,
) -> pd.DataFrame:
    """Return the winning model overall, or per group if ``group_by`` is set."""
    if metric not in metrics.columns:
        raise KeyError(
            f"Metric '{metric}' not in metrics columns: {list(metrics.columns)}"
        )
    if group_by is not None:
        idx = metrics.groupby(group_by)[metric].idxmin()
        return metrics.loc[idx].reset_index(drop=True)
    return metrics.loc[[metrics[metric].idxmin()]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Baseline comparison (vs LightGBM from notebook 06)
# ---------------------------------------------------------------------------


def compare_to_baseline(
    prophet_cv: pd.DataFrame,
    baseline_df: pd.DataFrame,
    baseline_cols: Optional[Sequence[str]] = None,
    y_true: str = "y",
    id_col: str = "unique_id",
    date_col: str = "ds",
    group_by: Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    """Join Prophet forecasts to the LightGBM baseline and rank all models.

    The Prophet backtest (``prophet_cv``) and the LightGBM output
    (``<scenario>_forecasts``) are aligned on ``[unique_id, ds]`` so both are scored
    on exactly the same observations.

    Parameters
    ----------
    prophet_cv
        Output of ``forecast_global`` / ``forecast_by_cluster``.
    baseline_df
        The ``<scenario>_forecasts`` table with ``y`` and ``y_hat_*`` columns.
    baseline_cols
        Which baseline prediction columns to include. Defaults to every
        ``y_hat_*`` column found in ``baseline_df``.
    group_by
        Optional grouping (e.g. ``"profile_cluster"``) for a per-segment ranking.

    Returns
    -------
    dict
        ``{"merged": DataFrame, "metrics": DataFrame, "winner": DataFrame}``.
    """
    if baseline_cols is None:
        baseline_cols = [c for c in baseline_df.columns if c.startswith("y_hat_")]
    if not baseline_cols:
        raise ValueError(
            "No baseline prediction columns found (expected 'y_hat_*'). "
            "Pass baseline_cols explicitly."
        )

    left = prophet_cv.copy()
    left[date_col] = pd.to_datetime(left[date_col])

    right = baseline_df[[id_col, date_col, *baseline_cols]].copy()
    right[date_col] = pd.to_datetime(right[date_col])

    merged = left.merge(right, on=[id_col, date_col], how="inner")
    if merged.empty:
        raise ValueError(
            "No overlapping (unique_id, ds) rows between Prophet forecasts and the "
            "baseline. Check that both cover the same backtest windows."
        )

    prophet_cols = [
        c
        for c in prophet_cv.columns
        if c not in _RESERVED and pd.api.types.is_numeric_dtype(prophet_cv[c])
    ]
    all_model_cols = [*prophet_cols, *baseline_cols]

    metrics = evaluate_forecasts(
        merged, model_cols=all_model_cols, y_true=y_true, group_by=group_by
    )
    metrics["family"] = np.where(
        metrics["model"].isin(baseline_cols), "LightGBM (baseline)", "Prophet"
    )
    winner = select_best(metrics, metric="MAE", group_by=group_by)
    return {"merged": merged, "metrics": metrics, "winner": winner}


# ---------------------------------------------------------------------------
# Narrative
# ---------------------------------------------------------------------------


def narrate_comparison(
    metrics: pd.DataFrame,
    winner: pd.DataFrame,
    metric: str = "MAE",
    unit: str = "units",
    group_by: Optional[str] = None,
) -> str:
    """Plain-language summary of the Prophet-vs-baseline benchmark."""
    lines: List[str] = []

    if group_by is None:
        best = winner.iloc[0]
        lines.append(
            f"Best model overall: **{best['model']}** "
            f"({best.get('family', 'n/a')}) with {metric}={best[metric]:.3f} {unit}."
        )
        baseline = metrics[metrics["family"] == "LightGBM (baseline)"]
        if not baseline.empty:
            b = baseline.sort_values(metric).iloc[0]
            delta = b[metric] - best[metric]
            direction = "better than" if delta > 0 else "worse than"
            lines.append(
                f"The best Prophet model is {direction} the best LightGBM baseline "
                f"({b['model']}, {metric}={b[metric]:.3f}) by {abs(delta):.3f} {unit}."
            )
    else:
        lines.append(f"Best model per {group_by} (by {metric}):")
        for _, row in winner.sort_values(group_by).iterrows():
            lines.append(
                f"  - {group_by}={row[group_by]}: **{row['model']}** "
                f"({row.get('family', 'n/a')}), {metric}={row[metric]:.3f} {unit}."
            )
        won = winner["family"].eq("Prophet").sum()
        total = len(winner)
        lines.append(
            f"Prophet wins in {won}/{total} {group_by} segments; "
            f"LightGBM wins the remaining {total - won}."
        )

    return "\n".join(lines)
