"""Moving-average forecasting utilities (window-average family).

Generate forecasts for time series using classic **moving-average** models — the
simple rolling-window mean and its seasonal variant — and benchmark them against
the pipeline's LightGBM baseline.

Built for the Time Series Forecasting Accelerator pipeline, where the panel has
``unique_id`` (series id), ``ds`` (date), ``y`` (actual value) and a
``profile_cluster`` grouping column (produced by notebooks 03/04). The LightGBM
baseline lives in ``<scenario>_forecasts`` as one or more ``y_hat_*`` columns
(notebook 06).

Two run scopes (both required by design)
----------------------------------------
1. **Global**  -- fit the moving-average models across the *entire* panel in a
   single ``StatsForecast`` run (``forecast_global``). Every series still gets its
   own fitted model (these models are inherently local), but selection and scoring
   are done pooled across all series.
2. **By profile-cluster** -- subset the panel by ``profile_cluster`` and run
   ``StatsForecast`` per cluster (``forecast_by_cluster``), so the *best*
   moving-average configuration can be chosen per cluster.

Models (from ``statsforecast.models``)
--------------------------------------
- ``WindowAverage``          : mean of the last ``window_size`` observations (SMA).
- ``SeasonalWindowAverage``  : mean of the last ``window_size`` same-season
                               observations (e.g. average of the last N Januaries).
Several window sizes are evaluated by default so the best span can be selected.
Optional naive baselines (``Naive``, ``SeasonalNaive``) can be added for context.

Metrics
-------
Headline metrics are scale-free / robust so they work across mixed-magnitude
series and remain defined when actuals are zero:

- ``MAE``   : mean absolute error            = mean(|y - yhat|)
- ``RMSE``  : root mean squared error        = sqrt(mean((y - yhat)^2))
- ``WMAPE`` : weighted MAPE                   = sum(|y - yhat|) / sum(|y|) * 100
- ``ME``    : mean error (bias)              = mean(y - yhat)

Error convention (Hyndman): ``error = y - yhat`` (actual minus forecast); a
positive ``ME`` means under-forecasting.

Public API
----------
- ``build_models``          : construct the list of moving-average model instances.
- ``forecast_global``       : backtest moving-average models on the whole panel (cross-validation).
- ``forecast_by_cluster``   : backtest moving-average models per ``profile_cluster``.
- ``predict_future``        : fit on all history and produce future-horizon forecasts.
- ``evaluate_forecasts``    : MAE / RMSE / WMAPE / ME per model column.
- ``select_best``           : pick the winning model overall or per group.
- ``compare_to_baseline``   : join moving-average forecasts to LightGBM ``y_hat_*`` and rank.
- ``narrate_comparison``    : plain-language summary of the benchmark.

``statsforecast`` is required for the forecasting functions. The evaluation and
narration helpers work on any tidy actuals-vs-predictions frame and have no
``statsforecast`` dependency.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Model catalogue
# ---------------------------------------------------------------------------

# Default window sizes for the simple moving average (WindowAverage) and the
# number of same-season periods for the seasonal moving average
# (SeasonalWindowAverage). Adjust to match the data granularity / seasonality.
DEFAULT_WINDOW_SIZES: Tuple[int, ...] = (3, 6, 12)
DEFAULT_SEASONAL_WINDOW_SIZES: Tuple[int, ...] = (2, 3)


def build_models(
    window_sizes: Optional[Sequence[int]] = None,
    seasonal_window_sizes: Optional[Sequence[int]] = None,
    season_length: int = 12,
    add_seasonal: bool = True,
    add_naive_baselines: bool = False,
):
    """Construct statsforecast moving-average model instances for the benchmark.

    Parameters
    ----------
    window_sizes
        Window spans for ``WindowAverage`` (simple moving average). Defaults to
        ``DEFAULT_WINDOW_SIZES``.
    seasonal_window_sizes
        Number of same-season periods for ``SeasonalWindowAverage``. Defaults to
        ``DEFAULT_SEASONAL_WINDOW_SIZES``.
    season_length
        Seasonal period (e.g. 12 for monthly data, 7 for daily-weekly). Used by
        ``SeasonalWindowAverage`` and ``SeasonalNaive``.
    add_seasonal
        If True, include ``SeasonalWindowAverage`` models.
    add_naive_baselines
        If True, append ``Naive`` and ``SeasonalNaive`` for reference.

    Returns
    -------
    list
        Instantiated ``statsforecast.models`` objects, ready for ``StatsForecast``.
        Each model is aliased (e.g. ``WindowAverage_3``) so its column is
        self-describing in the output frames.
    """
    from statsforecast.models import WindowAverage

    window_sizes = list(window_sizes) if window_sizes is not None else list(DEFAULT_WINDOW_SIZES)

    models = [
        WindowAverage(window_size=w, alias=f"WindowAverage_{w}") for w in window_sizes
    ]

    if add_seasonal:
        from statsforecast.models import SeasonalWindowAverage

        seasonal_window_sizes = (
            list(seasonal_window_sizes)
            if seasonal_window_sizes is not None
            else list(DEFAULT_SEASONAL_WINDOW_SIZES)
        )
        models += [
            SeasonalWindowAverage(
                season_length=season_length,
                window_size=w,
                alias=f"SeasonalWindowAverage_s{season_length}_w{w}",
            )
            for w in seasonal_window_sizes
        ]

    if add_naive_baselines:
        from statsforecast.models import Naive, SeasonalNaive

        models.append(Naive())
        models.append(SeasonalNaive(season_length=season_length))

    if not models:
        raise ValueError("No models were built. Provide window_sizes or enable seasonal/naive.")
    return models


def model_names(models) -> List[str]:
    """Return the string names statsforecast will use as output columns."""
    return [getattr(m, "alias", None) or m.__class__.__name__ for m in models]


# ---------------------------------------------------------------------------
# Forecasting — global scope (entire panel)
# ---------------------------------------------------------------------------

_PANEL_COLS = ["unique_id", "ds", "y"]


def _require_panel(df: pd.DataFrame, id_col: str, date_col: str, target: str) -> pd.DataFrame:
    """Return a clean statsforecast panel with canonical column names."""
    missing = [c for c in (id_col, date_col, target) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required column(s): {missing}")
    panel = df[[id_col, date_col, target]].rename(
        columns={id_col: "unique_id", date_col: "ds", target: "y"}
    )
    panel = panel.copy()
    panel["ds"] = pd.to_datetime(panel["ds"])
    return panel.sort_values(["unique_id", "ds"]).reset_index(drop=True)


def forecast_global(
    df: pd.DataFrame,
    h: int,
    freq: str = "MS",
    models=None,
    n_windows: int = 3,
    step_size: Optional[int] = None,
    id_col: str = "unique_id",
    date_col: str = "ds",
    target: str = "y",
    n_jobs: int = -1,
):
    """Backtest moving-average models on the ENTIRE panel via cross-validation.

    Uses ``StatsForecast.cross_validation`` so every prediction is out-of-sample
    and carries the matching actual ``y`` and ``cutoff`` — this is what makes the
    result directly comparable to the LightGBM baseline on the same windows.

    Parameters
    ----------
    df
        Panel with id / date / target columns (extra columns are ignored).
    h
        Forecast horizon (number of periods per window).
    freq
        Pandas offset alias matching the data granularity (e.g. ``"MS"`` monthly).
    models
        List of statsforecast models; defaults to ``build_models()``.
    n_windows, step_size
        Rolling-origin backtest configuration. ``step_size`` defaults to ``h``.
    n_jobs
        Parallelism passed to ``StatsForecast``.

    Returns
    -------
    pandas.DataFrame
        Cross-validation frame with columns ``unique_id``, ``ds``, ``cutoff``,
        ``y`` and one column per model. ``scope`` is set to ``"global"``.
    """
    from statsforecast import StatsForecast

    panel = _require_panel(df, id_col, date_col, target)
    models = models if models is not None else build_models()
    step_size = step_size if step_size is not None else h

    sf = StatsForecast(models=models, freq=freq, n_jobs=n_jobs)
    cv = sf.cross_validation(
        df=panel, h=h, n_windows=n_windows, step_size=step_size
    )
    cv = cv.reset_index() if "unique_id" not in cv.columns else cv
    cv["scope"] = "global"
    return cv


# ---------------------------------------------------------------------------
# Forecasting — by profile_cluster
# ---------------------------------------------------------------------------


def forecast_by_cluster(
    df: pd.DataFrame,
    h: int,
    group_col: str = "profile_cluster",
    freq: str = "MS",
    models=None,
    n_windows: int = 3,
    step_size: Optional[int] = None,
    id_col: str = "unique_id",
    date_col: str = "ds",
    target: str = "y",
    n_jobs: int = -1,
):
    """Backtest moving-average models PER ``profile_cluster``.

    Runs one ``StatsForecast.cross_validation`` per cluster so the best
    moving-average configuration can be selected per cluster (see ``select_best``).
    The combined result carries the ``profile_cluster`` label alongside each row.

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

    models = models if models is not None else build_models()
    step_size = step_size if step_size is not None else h

    # Map each unique_id to its cluster so we can re-attach the label to the
    # canonical (renamed) panel returned by cross_validation.
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
            n_jobs=n_jobs,
        )
        cv["profile_cluster"] = cluster_id
        cv["scope"] = f"cluster:{cluster_id}"
        frames.append(cv)

    if not frames:
        raise ValueError("No clusters produced any forecasts.")

    out = pd.concat(frames, ignore_index=True)
    # Ensure profile_cluster is populated even if groupby key was NaN.
    out["profile_cluster"] = out["profile_cluster"].fillna(
        out["unique_id"].map(id_to_cluster)
    )
    return out


def predict_future(
    df: pd.DataFrame,
    h: int,
    freq: str = "MS",
    models=None,
    id_col: str = "unique_id",
    date_col: str = "ds",
    target: str = "y",
    n_jobs: int = -1,
) -> pd.DataFrame:
    """Fit on all history and produce genuine future-horizon forecasts.

    Use this once a model has been selected; unlike the ``forecast_*`` backtests
    this returns forward-looking predictions with no matching actuals.
    """
    from statsforecast import StatsForecast

    panel = _require_panel(df, id_col, date_col, target)
    models = models if models is not None else build_models()
    sf = StatsForecast(models=models, freq=freq, n_jobs=n_jobs)
    fc = sf.forecast(df=panel, h=h)
    return fc.reset_index() if "unique_id" not in fc.columns else fc


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
    reserved = {"unique_id", "ds", "cutoff", y_true, "scope", "profile_cluster"}
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
        return pd.DataFrame(out_rows)[cols].sort_values([group_by, "MAE"]).reset_index(drop=True)

    return pd.DataFrame(_score(cv_df)).sort_values("MAE").reset_index(drop=True)


def select_best(
    metrics: pd.DataFrame,
    metric: str = "MAE",
    group_by: Optional[str] = None,
) -> pd.DataFrame:
    """Return the winning model overall, or per group if ``group_by`` is set."""
    if metric not in metrics.columns:
        raise KeyError(f"Metric '{metric}' not in metrics columns: {list(metrics.columns)}")
    if group_by is not None:
        idx = metrics.groupby(group_by)[metric].idxmin()
        return metrics.loc[idx].reset_index(drop=True)
    return metrics.loc[[metrics[metric].idxmin()]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Baseline comparison (vs LightGBM from notebook 06)
# ---------------------------------------------------------------------------


def compare_to_baseline(
    moving_average_cv: pd.DataFrame,
    baseline_df: pd.DataFrame,
    baseline_cols: Optional[Sequence[str]] = None,
    y_true: str = "y",
    id_col: str = "unique_id",
    date_col: str = "ds",
    group_by: Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    """Join moving-average forecasts to the LightGBM baseline and rank all models.

    The moving-average backtest (``moving_average_cv``) and the LightGBM output
    (``<scenario>_forecasts``) are aligned on ``[unique_id, ds]`` so both are
    scored on exactly the same observations.

    Parameters
    ----------
    moving_average_cv
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

    left = moving_average_cv.copy()
    left[date_col] = pd.to_datetime(left[date_col])

    right = baseline_df[[id_col, date_col, *baseline_cols]].copy()
    right[date_col] = pd.to_datetime(right[date_col])

    merged = left.merge(right, on=[id_col, date_col], how="inner")
    if merged.empty:
        raise ValueError(
            "No overlapping (unique_id, ds) rows between moving-average forecasts "
            "and the baseline. Check that both cover the same backtest windows."
        )

    ma_cols = [
        c
        for c in moving_average_cv.columns
        if c not in {"unique_id", "ds", "cutoff", y_true, "scope", "profile_cluster"}
        and pd.api.types.is_numeric_dtype(moving_average_cv[c])
    ]
    all_model_cols = [*ma_cols, *baseline_cols]

    metrics = evaluate_forecasts(
        merged, model_cols=all_model_cols, y_true=y_true, group_by=group_by
    )
    metrics["family"] = np.where(
        metrics["model"].isin(baseline_cols), "LightGBM (baseline)", "MovingAverage"
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
    """Plain-language summary of the moving-average-vs-baseline benchmark."""
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
            delta = (b[metric] - best[metric])
            direction = "better than" if delta > 0 else "worse than"
            lines.append(
                f"The best moving-average model is {direction} the best LightGBM "
                f"baseline ({b['model']}, {metric}={b[metric]:.3f}) by "
                f"{abs(delta):.3f} {unit}."
            )
    else:
        lines.append(f"Best model per {group_by} (by {metric}):")
        for _, row in winner.sort_values(group_by).iterrows():
            lines.append(
                f"  - {group_by}={row[group_by]}: **{row['model']}** "
                f"({row.get('family', 'n/a')}), {metric}={row[metric]:.3f} {unit}."
            )
        won = winner["family"].eq("MovingAverage").sum()
        total = len(winner)
        lines.append(
            f"Moving-average models win in {won}/{total} {group_by} segments; "
            f"LightGBM wins the remaining {total - won}."
        )

    return "\n".join(lines)
