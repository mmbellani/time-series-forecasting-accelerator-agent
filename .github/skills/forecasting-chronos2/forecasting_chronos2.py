"""Foundation-model forecasting utilities (Chronos-2 & relatives).

Generate zero-shot forecasts for time series using a pretrained time-series
foundation model (Chronos-2), and benchmark them against the pipeline's LightGBM
baseline.

Built for the Time Series Forecasting Accelerator pipeline, where the panel has
``unique_id`` (series id), ``ds`` (date), ``y`` (actual value) and a
``profile_cluster`` grouping column (produced by notebooks 03/04). The LightGBM
baseline lives in ``<scenario>_forecasts`` as one or more ``y_hat_*`` columns
(notebook 06).

Two run scopes (both required by design)
----------------------------------------
1. **Global**  -- feed the *entire* panel to Chronos-2 in a single ``predict_df``
   call (``forecast_global``). Because Chronos-2 uses a **group-attention
   mechanism for in-context learning across related series**, passing all series
   together lets the model cross-learn across the whole dataset.
2. **By profile-cluster** -- subset the panel by ``profile_cluster`` and call
   Chronos-2 once per cluster (``forecast_by_cluster``), so the model's
   in-context learning is confined to (and specialised for) each cluster.

Unlike classic local models (e.g. Croston), the global vs. per-cluster split
genuinely changes the model's *in-context set* — not just the scoring scope.

Model (from ``chronos``)
------------------------
- ``amazon/chronos-2`` : 120M-parameter encoder-only time-series foundation model.
  Zero-shot univariate, multivariate and covariate-informed forecasting. Loaded
  via ``chronos.Chronos2Pipeline`` and queried with the pandas ``predict_df`` API.
Other Chronos family checkpoints (e.g. ``amazon/chronos-bolt-base``) can be added
through ``build_models`` for a multi-model comparison.

Metrics
-------
The headline metrics are scale-free / robust so they compare fairly against the
LightGBM baseline (and remain well-defined on series with zero periods):

- ``MAE``   : mean absolute error            = mean(|y - yhat|)
- ``RMSE``  : root mean squared error        = sqrt(mean((y - yhat)^2))
- ``WMAPE`` : weighted MAPE                   = sum(|y - yhat|) / sum(|y|) * 100
- ``ME``    : mean error (bias)              = mean(y - yhat)

Error convention (Hyndman): ``error = y - yhat`` (actual minus forecast); a
positive ``ME`` means under-forecasting.

Public API
----------
- ``build_models``          : construct the list of Chronos foundation-model wrappers.
- ``forecast_global``       : backtest Chronos on the whole panel (rolling-origin CV).
- ``forecast_by_cluster``   : backtest Chronos per ``profile_cluster``.
- ``predict_future``        : produce genuine future-horizon forecasts from full history.
- ``evaluate_forecasts``    : MAE / RMSE / WMAPE / ME per model column.
- ``select_best``           : pick the winning model overall or per group.
- ``compare_to_baseline``   : join Chronos forecasts to LightGBM ``y_hat_*`` and rank.
- ``narrate_comparison``    : plain-language summary of the benchmark.

``chronos-forecasting>=2.0`` (which provides ``Chronos2Pipeline``) and ``torch``
are required for the forecasting functions. The evaluation and narration helpers
work on any tidy actuals-vs-predictions frame and have no ``chronos`` dependency.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Model catalogue
# ---------------------------------------------------------------------------

# Default foundation model(s) to evaluate. Chronos-2 is the primary model;
# additional Chronos checkpoints can be added for a multi-model comparison.
DEFAULT_CHRONOS_MODELS: List[str] = [
    "amazon/chronos-2",
]

# Friendly, column-safe aliases used as the model's output column name.
_DEFAULT_ALIASES: Dict[str, str] = {
    "amazon/chronos-2": "Chronos2",
    "autogluon/chronos-2-small": "Chronos2Small",
    "autogluon/chronos-2-synth": "Chronos2Synth",
    "amazon/chronos-bolt-base": "ChronosBoltBase",
    "amazon/chronos-bolt-small": "ChronosBoltSmall",
}


def _clean_alias(model_name: str) -> str:
    """Turn a HF model id into a column-safe alias (e.g. amazon/chronos-2 -> Chronos2)."""
    if model_name in _DEFAULT_ALIASES:
        return _DEFAULT_ALIASES[model_name]
    base = model_name.split("/")[-1]
    parts = [p for p in base.replace(".", "-").split("-") if p]
    return "".join(p.capitalize() for p in parts)


class ChronosForecaster:
    """Thin wrapper around a Chronos pipeline exposing a uniform ``predict_df``.

    The pipeline is loaded lazily on first use so that constructing the model list
    (and importing this module) does not require ``chronos`` / GPU resources.

    Parameters
    ----------
    model_name
        Hugging Face model id (e.g. ``"amazon/chronos-2"``).
    device_map
        Device placement passed to ``from_pretrained`` (``"auto"``, ``"cuda"``,
        ``"cpu"``). Chronos-2 supports both GPU and CPU inference.
    quantile_levels
        Quantile levels to request; the median (0.5) is used as the point forecast.
    torch_dtype
        Optional dtype name (e.g. ``"bfloat16"``) resolved against ``torch``.
    alias
        Output column name; defaults to a cleaned version of ``model_name``.
    """

    def __init__(
        self,
        model_name: str = "amazon/chronos-2",
        device_map: str = "auto",
        quantile_levels: Sequence[float] = (0.1, 0.5, 0.9),
        torch_dtype: Optional[str] = None,
        alias: Optional[str] = None,
    ):
        self.model_name = model_name
        self.device_map = device_map
        self.quantile_levels = list(quantile_levels)
        self.torch_dtype = torch_dtype
        self.alias = alias or _clean_alias(model_name)
        self._pipeline = None

    @property
    def name(self) -> str:
        return self.alias

    def _ensure_pipeline(self):
        if self._pipeline is None:
            from chronos import Chronos2Pipeline

            kwargs: Dict[str, object] = {"device_map": self.device_map}
            if self.torch_dtype is not None:
                import torch

                kwargs["torch_dtype"] = getattr(torch, self.torch_dtype)
            self._pipeline = Chronos2Pipeline.from_pretrained(self.model_name, **kwargs)
        return self._pipeline

    def predict_df(
        self,
        context_df: pd.DataFrame,
        h: int,
        id_column: str = "unique_id",
        timestamp_column: str = "ds",
        target: str = "y",
        future_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Zero-shot forecast ``h`` steps ahead for every series in ``context_df``.

        Returns the raw ``predict_df`` output (id + timestamp + quantile columns).
        """
        pipe = self._ensure_pipeline()
        return pipe.predict_df(
            context_df,
            future_df=future_df,
            prediction_length=h,
            quantile_levels=self.quantile_levels,
            id_column=id_column,
            timestamp_column=timestamp_column,
            target=target,
        )


def build_models(
    model_names: Optional[Sequence[str]] = None,
    device_map: str = "auto",
    quantile_levels: Sequence[float] = (0.1, 0.5, 0.9),
    torch_dtype: Optional[str] = None,
    aliases: Optional[Dict[str, str]] = None,
) -> List[ChronosForecaster]:
    """Construct Chronos foundation-model wrappers for the benchmark.

    Parameters
    ----------
    model_names
        Hugging Face model ids. Defaults to ``["amazon/chronos-2"]``.
    device_map, quantile_levels, torch_dtype
        Passed through to each :class:`ChronosForecaster`.
    aliases
        Optional ``{model_name: column_alias}`` overrides.

    Returns
    -------
    list[ChronosForecaster]
        Lazily-loaded model wrappers, ready for ``forecast_global`` / ``forecast_by_cluster``.
    """
    names = list(model_names) if model_names is not None else list(DEFAULT_CHRONOS_MODELS)
    aliases = aliases or {}
    return [
        ChronosForecaster(
            model_name=n,
            device_map=device_map,
            quantile_levels=quantile_levels,
            torch_dtype=torch_dtype,
            alias=aliases.get(n),
        )
        for n in names
    ]


def model_names(models: Sequence[ChronosForecaster]) -> List[str]:
    """Return the output column names the models will produce."""
    return [m.name for m in models]


# ---------------------------------------------------------------------------
# Panel helpers
# ---------------------------------------------------------------------------

_RESERVED = {"unique_id", "ds", "cutoff", "y", "scope", "profile_cluster"}


def _require_panel(df: pd.DataFrame, id_col: str, date_col: str, target: str) -> pd.DataFrame:
    """Return a clean panel with canonical column names (unique_id / ds / y)."""
    missing = [c for c in (id_col, date_col, target) if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required column(s): {missing}")
    panel = df[[id_col, date_col, target]].rename(
        columns={id_col: "unique_id", date_col: "ds", target: "y"}
    ).copy()
    panel["ds"] = pd.to_datetime(panel["ds"])
    return panel.sort_values(["unique_id", "ds"]).reset_index(drop=True)


def _rolling_cutoffs(
    dates_sorted: np.ndarray, h: int, n_windows: int, step_size: Optional[int]
) -> List[Tuple[pd.Timestamp, List[pd.Timestamp]]]:
    """Build rolling-origin (cutoff, test_dates) pairs from the global date grid.

    Mirrors statsforecast cross-validation semantics: window ``i`` tests the ``h``
    dates ending ``i * step_size`` positions from the end of the series.
    """
    step_size = step_size if step_size is not None else h
    length = len(dates_sorted)
    windows: List[Tuple[pd.Timestamp, List[pd.Timestamp]]] = []
    for i in range(n_windows):
        end = length - i * step_size          # exclusive end index of the test slice
        start = end - h                        # inclusive start index of the test slice
        if start <= 0:
            break
        cutoff = pd.Timestamp(dates_sorted[start - 1])
        test_dates = [pd.Timestamp(d) for d in dates_sorted[start:end]]
        windows.append((cutoff, test_dates))
    return windows


def _point_col(pred_df: pd.DataFrame, quantile_point: float = 0.5) -> str:
    """Locate the point-forecast column in a Chronos ``predict_df`` output."""
    candidates = [
        str(quantile_point),
        f"{quantile_point:g}",
        f"{quantile_point:.1f}",
        "0.5",
        "predictions",
        "mean",
    ]
    for c in candidates:
        if c in pred_df.columns:
            return c
    numeric = [
        c
        for c in pred_df.columns
        if c not in _RESERVED and pd.api.types.is_numeric_dtype(pred_df[c])
    ]
    if not numeric:
        raise ValueError(
            f"Could not find a point-forecast column in predict_df output. "
            f"Columns: {list(pred_df.columns)}"
        )
    return numeric[-1]


# ---------------------------------------------------------------------------
# Forecasting — global scope (entire panel)
# ---------------------------------------------------------------------------


def forecast_global(
    df: pd.DataFrame,
    h: int,
    freq: str = "MS",
    models: Optional[Sequence[ChronosForecaster]] = None,
    n_windows: int = 3,
    step_size: Optional[int] = None,
    id_col: str = "unique_id",
    date_col: str = "ds",
    target: str = "y",
    quantile_point: float = 0.5,
) -> pd.DataFrame:
    """Backtest Chronos on the ENTIRE panel via rolling-origin cross-validation.

    For every window the model receives the full history up to the cutoff for
    **all** series at once (Chronos-2 cross-learns across items via group
    attention), forecasts ``h`` steps, and the predictions are aligned with the
    held-out actuals — making the result directly comparable to the LightGBM
    baseline on the same windows.

    Parameters
    ----------
    df
        Panel with id / date / target columns (extra columns are ignored).
    h
        Forecast horizon (number of periods per window).
    freq
        Pandas offset alias matching the data granularity (e.g. ``"MS"`` monthly).
        Retained for parity/reporting; Chronos infers step spacing from timestamps.
    models
        List of :class:`ChronosForecaster`; defaults to ``build_models()``.
    n_windows, step_size
        Rolling-origin backtest configuration. ``step_size`` defaults to ``h``.
    quantile_point
        Quantile used as the point forecast (default median 0.5).

    Returns
    -------
    pandas.DataFrame
        CV frame with ``unique_id``, ``ds``, ``cutoff``, ``y`` and one column per
        model. ``scope`` is set to ``"global"``.
    """
    panel = _require_panel(df, id_col, date_col, target)
    models = list(models) if models is not None else build_models()

    dates_sorted = np.array(sorted(pd.unique(panel["ds"])))
    windows = _rolling_cutoffs(dates_sorted, h, n_windows, step_size)
    if not windows:
        raise ValueError(
            "No backtest windows could be built. Reduce h / n_windows or provide "
            "more history."
        )

    frames: List[pd.DataFrame] = []
    for cutoff, test_dates in windows:
        context_df = panel[panel["ds"] <= cutoff]
        test_set = set(pd.Timestamp(d) for d in test_dates)
        base = panel[panel["ds"].isin(test_set)][["unique_id", "ds", "y"]].copy()
        base["cutoff"] = cutoff

        for model in models:
            pred = model.predict_df(
                context_df, h=h, id_column="unique_id", timestamp_column="ds", target="y"
            )
            pcol = _point_col(pred, quantile_point)
            pred_small = pred[["unique_id", "ds", pcol]].rename(columns={pcol: model.name})
            pred_small["ds"] = pd.to_datetime(pred_small["ds"])
            base = base.merge(pred_small, on=["unique_id", "ds"], how="left")

        frames.append(base)

    out = pd.concat(frames, ignore_index=True)
    out["scope"] = "global"
    return out


# ---------------------------------------------------------------------------
# Forecasting — by profile_cluster
# ---------------------------------------------------------------------------


def forecast_by_cluster(
    df: pd.DataFrame,
    h: int,
    group_col: str = "profile_cluster",
    freq: str = "MS",
    models: Optional[Sequence[ChronosForecaster]] = None,
    n_windows: int = 3,
    step_size: Optional[int] = None,
    id_col: str = "unique_id",
    date_col: str = "ds",
    target: str = "y",
    quantile_point: float = 0.5,
) -> pd.DataFrame:
    """Backtest Chronos PER ``profile_cluster``.

    Runs one rolling-origin backtest per cluster so Chronos-2's in-context
    learning is confined to each cluster. The combined result carries the
    ``profile_cluster`` label alongside each row.

    Returns
    -------
    pandas.DataFrame
        CV frame with ``unique_id``, ``ds``, ``cutoff``, ``y``, one column per
        model, plus ``profile_cluster`` and ``scope`` (``"cluster:<id>"``).
    """
    if group_col not in df.columns:
        raise KeyError(
            f"Grouping column '{group_col}' not found. Available: {list(df.columns)}"
        )

    models = list(models) if models is not None else build_models()

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
            quantile_point=quantile_point,
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
    models: Optional[Sequence[ChronosForecaster]] = None,
    id_col: str = "unique_id",
    date_col: str = "ds",
    target: str = "y",
    quantile_point: float = 0.5,
) -> pd.DataFrame:
    """Produce genuine future-horizon forecasts from the full history.

    Use this once a model has been selected; unlike the ``forecast_*`` backtests
    this returns forward-looking predictions with no matching actuals.

    Returns
    -------
    pandas.DataFrame
        ``unique_id``, ``ds`` and one point-forecast column per model.
    """
    panel = _require_panel(df, id_col, date_col, target)
    models = list(models) if models is not None else build_models()

    out: Optional[pd.DataFrame] = None
    for model in models:
        pred = model.predict_df(
            panel, h=h, id_column="unique_id", timestamp_column="ds", target="y"
        )
        pcol = _point_col(pred, quantile_point)
        pred_small = pred[["unique_id", "ds", pcol]].rename(columns={pcol: model.name})
        pred_small["ds"] = pd.to_datetime(pred_small["ds"])
        out = pred_small if out is None else out.merge(pred_small, on=["unique_id", "ds"], how="outer")
    return out.sort_values(["unique_id", "ds"]).reset_index(drop=True)


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
    reserved = set(_RESERVED) | {y_true}
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
        raise KeyError(f"Metric '{metric}' not in metrics columns: {list(metrics.columns)}")
    if group_by is not None:
        idx = metrics.groupby(group_by)[metric].idxmin()
        return metrics.loc[idx].reset_index(drop=True)
    return metrics.loc[[metrics[metric].idxmin()]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Baseline comparison (vs LightGBM from notebook 06)
# ---------------------------------------------------------------------------


def compare_to_baseline(
    chronos_cv: pd.DataFrame,
    baseline_df: pd.DataFrame,
    baseline_cols: Optional[Sequence[str]] = None,
    y_true: str = "y",
    id_col: str = "unique_id",
    date_col: str = "ds",
    group_by: Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    """Join Chronos forecasts to the LightGBM baseline and rank all models.

    The Chronos backtest (``chronos_cv``) and the LightGBM output
    (``<scenario>_forecasts``) are aligned on ``[unique_id, ds]`` so both are
    scored on exactly the same observations.

    Parameters
    ----------
    chronos_cv
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

    left = chronos_cv.copy()
    left[date_col] = pd.to_datetime(left[date_col])

    right = baseline_df[[id_col, date_col, *baseline_cols]].copy()
    right[date_col] = pd.to_datetime(right[date_col])

    merged = left.merge(right, on=[id_col, date_col], how="inner")
    if merged.empty:
        raise ValueError(
            "No overlapping (unique_id, ds) rows between Chronos forecasts and the "
            "baseline. Check that both cover the same backtest windows."
        )

    reserved = set(_RESERVED) | {y_true}
    chronos_cols = [
        c
        for c in chronos_cv.columns
        if c not in reserved and pd.api.types.is_numeric_dtype(chronos_cv[c])
    ]
    all_model_cols = [*chronos_cols, *baseline_cols]

    metrics = evaluate_forecasts(
        merged, model_cols=all_model_cols, y_true=y_true, group_by=group_by
    )
    metrics["family"] = np.where(
        metrics["model"].isin(baseline_cols), "LightGBM (baseline)", "Chronos (foundation)"
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
    """Plain-language summary of the Chronos-vs-baseline benchmark."""
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
                f"The best Chronos model is {direction} the best LightGBM baseline "
                f"({b['model']}, {metric}={b[metric]:.3f}) by {abs(delta):.3f} {unit}."
            )
    else:
        lines.append(f"Best model per {group_by} (by {metric}):")
        for _, row in winner.sort_values(group_by).iterrows():
            lines.append(
                f"  - {group_by}={row[group_by]}: **{row['model']}** "
                f"({row.get('family', 'n/a')}), {metric}={row[metric]:.3f} {unit}."
            )
        won = winner["family"].eq("Chronos (foundation)").sum()
        total = len(winner)
        lines.append(
            f"Chronos wins in {won}/{total} {group_by} segments; "
            f"LightGBM wins the remaining {total - won}."
        )

    return "\n".join(lines)
