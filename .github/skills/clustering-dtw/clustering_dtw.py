"""Dynamic Time Warping (DTW) clustering utilities for regular time series.

Alternative to the Euclidean **K-Means** clustering in **notebook 04
(04 Clustering)**. It follows the *same* pipeline shape — filter to the
``regular`` (smooth) profiles, winsorize, standardize, build a series x time
matrix, choose the number of clusters, fit, and write ``profile_cluster`` back
onto the profiling table — but swaps the distance/assignment step from
Euclidean K-Means to **DTW-based** ``TimeSeriesKMeans`` (``tslearn``).

Why DTW instead of Euclidean K-Means
------------------------------------
Euclidean K-Means compares two series **point-by-point at the same timestamp**,
so two series with the *same shape* but a small phase shift (a peak one week
early, a season starting late) look far apart. **Dynamic Time Warping** aligns
series by *elastically stretching/compressing the time axis*, so it groups series
by **shape/pattern** rather than by exact temporal alignment. This is a better
fit when the drivers of consumption (promotions, holidays, weather) hit different
series with slightly different timing.

Built for the Time Series Forecasting Accelerator pipeline. Inputs mirror
notebook 04:

- ``df_final``      : the prepared panel with ``unique_id``, ``date_var``, ``y``.
- ``df_profiling``  : the profiling table with a ``profile`` column classifying
                      each ``unique_id`` as ``regular`` / ``intermittent`` / etc.

Output mirrors notebook 04: ``df_profiling`` plus a ``profile_cluster`` column,
where regular series carry their DTW cluster id and every other profile keeps its
original profile label.

Pipeline (mirrors notebook 04, DTW-swapped)
-------------------------------------------
1. ``filter_regular_series``   -- keep only series labelled ``regular``.
2. ``build_series_matrix``     -- winsorize + standardize + pivot to a dense
                                  (n_series, n_timestamps, 1) array with no NaN.
3. ``choose_n_clusters``       -- elbow (inertia) + **DTW silhouette** sweep.
4. ``fit_dtw_clusters``        -- fit ``TimeSeriesKMeans(metric="dtw")``.
5. ``assign_profile_cluster``  -- merge cluster ids back, build ``profile_cluster``.
6. ``cluster_summary`` / ``narrate_clusters`` -- describe the result.

Dependencies
------------
- ``tslearn`` (>=0.6.3) provides ``TimeSeriesKMeans``, ``silhouette_score`` and
  ``TimeSeriesScalerMeanVariance``. It is **not yet** in ``requirements.txt`` --
  flag it as a new dependency and install before running:  ``pip install tslearn``.
- ``scipy`` (winsorize) and ``kneed`` (elbow) are already in the pipeline.

Public API
----------
- ``filter_regular_series``  : subset the panel to the regular/smooth profiles.
- ``build_series_matrix``    : winsorize, standardize, pivot to a dense 3-D array.
- ``build_dtw_model``        : construct a configured ``TimeSeriesKMeans``.
- ``choose_n_clusters``      : elbow (inertia) + DTW silhouette diagnostics.
- ``fit_dtw_clusters``       : fit DTW clustering, return per-series labels.
- ``assign_profile_cluster`` : merge labels into ``profile_cluster`` (NB04 output).
- ``cluster_summary``        : per-cluster series counts.
- ``narrate_clusters``       : plain-language summary of the clustering.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Defaults (aligned with notebook 04)
# ---------------------------------------------------------------------------
DEFAULT_WINSOR_LIMITS: Tuple[float, float] = (0.05, 0.05)  # (lowest, highest)
DEFAULT_RANDOM_STATE: int = 42
DEFAULT_METRIC: str = "dtw"  # "dtw" | "softdtw" | "euclidean"


# ---------------------------------------------------------------------------
# 1. Filter to regular / smooth series
# ---------------------------------------------------------------------------
def filter_regular_series(
    df_final: pd.DataFrame,
    df_profiling: pd.DataFrame,
    unique_id: str,
    profile_col: str = "profile",
    regular_label: str = "regular",
) -> Tuple[pd.DataFrame, List]:
    """Restrict the panel to the series classified as ``regular`` (smooth).

    Mirrors notebook 04: only smooth/regular series are clustered; intermittent,
    lumpy, erratic and unforecastable series keep their profile label.

    Parameters
    ----------
    df_final
        Prepared panel with at least ``unique_id`` and the target column.
    df_profiling
        Profiling table with one row per ``unique_id`` and a ``profile`` column.
    unique_id
        Series id column shared by both frames.
    profile_col
        Column in ``df_profiling`` holding the profile label. Default ``"profile"``.
    regular_label
        Value marking a regular/smooth series. Default ``"regular"``.

    Returns
    -------
    (df_regular, regular_ids)
        The subset of ``df_final`` for regular series, and the list of their ids.
    """
    regular_ids = list(
        df_profiling.loc[df_profiling[profile_col] == regular_label, unique_id].unique()
    )
    mask = df_final[unique_id].isin(regular_ids)
    df_regular = df_final.loc[mask].copy()
    return df_regular, regular_ids


# ---------------------------------------------------------------------------
# 2. Build the (n_series, n_timestamps, 1) matrix
# ---------------------------------------------------------------------------
def build_series_matrix(
    df: pd.DataFrame,
    unique_id: str,
    date_var: str,
    y: str,
    winsor_limits: Tuple[float, float] = DEFAULT_WINSOR_LIMITS,
    standardize: bool = True,
) -> Tuple[np.ndarray, List, pd.DataFrame]:
    """Winsorize, standardize and pivot the panel into a dense 3-D DTW array.

    Reproduces the notebook 04 preprocessing (winsorize the tails, per-series
    standardization to remove level/scale so clustering keys on *shape*), then
    returns the array shape ``tslearn`` expects.

    Parameters
    ----------
    df
        Long panel restricted to the series to cluster (e.g. output of
        :func:`filter_regular_series`).
    unique_id, date_var, y
        Column names for the series id, the date, and the target value.
    winsor_limits
        ``(lowest, highest)`` fraction to winsorize per (series, date). Default
        ``(0.05, 0.05)`` matches the notebook.
    standardize
        If ``True`` (default) apply per-series mean/variance standardization
        (``TimeSeriesScalerMeanVariance``) so clustering is scale-invariant.

    Returns
    -------
    (X, ids, wide_df)
        ``X``      : ``np.ndarray`` of shape ``(n_series, n_timestamps, 1)`` with no NaN.
        ``ids``    : list of ``unique_id`` values aligned to ``X`` rows.
        ``wide_df``: the intermediate wide (date x series) frame for inspection.
    """
    from scipy.stats.mstats import winsorize

    low, high = winsor_limits

    # Winsorize per (series, date) exactly as the notebook does, then aggregate.
    df_win = (
        df.groupby([unique_id, date_var])[y]
        .apply(lambda x: np.sum(winsorize(x, (low, high))))
        .reset_index()
    )
    df_win.columns = [unique_id, date_var, y]

    # Wide matrix: rows = dates, columns = series.
    wide_df = df_win.pivot(index=date_var, columns=unique_id, values=y)

    # Only series with a complete history can be clustered (no NaN allowed).
    wide_df = wide_df.dropna(axis=1, how="any")
    ids = list(wide_df.columns)

    # Series x time; tslearn wants (n_series, sz, dim).
    X = wide_df.to_numpy().T  # (n_series, n_timestamps)
    X = X[:, :, np.newaxis].astype(float)

    if standardize:
        from tslearn.preprocessing import TimeSeriesScalerMeanVariance

        X = TimeSeriesScalerMeanVariance().fit_transform(X)

    return X, ids, wide_df


# ---------------------------------------------------------------------------
# 3. Model factory
# ---------------------------------------------------------------------------
def build_dtw_model(
    n_clusters: int,
    metric: str = DEFAULT_METRIC,
    max_iter: int = 50,
    n_init: int = 3,
    random_state: int = DEFAULT_RANDOM_STATE,
    sakoe_chiba_radius: Optional[int] = None,
    metric_params: Optional[dict] = None,
):
    """Construct a configured ``tslearn`` ``TimeSeriesKMeans`` for DTW clustering.

    Parameters
    ----------
    n_clusters
        Number of clusters (``k``).
    metric
        ``"dtw"`` (default), ``"softdtw"`` or ``"euclidean"``. DTW clusters by
        shape and is robust to phase shifts; ``euclidean`` reproduces the classic
        notebook-04 behaviour and is useful as a sanity check.
    max_iter, n_init, random_state
        Standard K-Means controls. DTW is expensive, so ``n_init`` defaults low.
    sakoe_chiba_radius
        Optional Sakoe-Chiba band radius that constrains the warping window. A
        small radius speeds DTW up dramatically and prevents pathological
        alignments; ``None`` leaves DTW unconstrained.
    metric_params
        Extra params forwarded to the metric (merged with ``sakoe_chiba_radius``).

    Returns
    -------
    tslearn.clustering.TimeSeriesKMeans
        An unfitted, configured model.
    """
    from tslearn.clustering import TimeSeriesKMeans

    params = dict(metric_params or {})
    if sakoe_chiba_radius is not None and metric in ("dtw", "softdtw"):
        params.setdefault("global_constraint", "sakoe_chiba")
        params.setdefault("sakoe_chiba_radius", sakoe_chiba_radius)

    return TimeSeriesKMeans(
        n_clusters=n_clusters,
        metric=metric,
        max_iter=max_iter,
        n_init=n_init,
        random_state=random_state,
        metric_params=params or None,
    )


# ---------------------------------------------------------------------------
# 4. Choose the number of clusters (elbow + DTW silhouette)
# ---------------------------------------------------------------------------
def choose_n_clusters(
    X: np.ndarray,
    k_range: Optional[Sequence[int]] = None,
    metric: str = DEFAULT_METRIC,
    random_state: int = DEFAULT_RANDOM_STATE,
    sakoe_chiba_radius: Optional[int] = None,
    max_iter: int = 50,
    n_init: int = 3,
) -> Dict[str, object]:
    """Sweep ``k`` and report elbow (inertia) and DTW-silhouette diagnostics.

    The silhouette is computed with ``tslearn``'s DTW-aware ``silhouette_score``
    so cohesion/separation are measured under the *same* distance used to
    cluster — not Euclidean.

    Parameters
    ----------
    X
        ``(n_series, n_timestamps, 1)`` array from :func:`build_series_matrix`.
    k_range
        Candidate cluster counts. Defaults to ``range(2, min(8, n_series))``.
    metric, random_state, sakoe_chiba_radius, max_iter, n_init
        Passed through to :func:`build_dtw_model`.

    Returns
    -------
    dict
        Keys: ``k_values``, ``inertias``, ``silhouettes``, ``elbow_k``,
        ``silhouette_k``, ``suggested_k`` (``max`` of the two, matching notebook 04).
    """
    from tslearn.clustering import silhouette_score

    n_series = X.shape[0]
    if k_range is None:
        k_range = list(range(2, max(3, min(8, n_series))))
    k_values = list(k_range)

    inertias: List[float] = []
    silhouettes: List[float] = []
    for k in k_values:
        model = build_dtw_model(
            n_clusters=k,
            metric=metric,
            max_iter=max_iter,
            n_init=n_init,
            random_state=random_state,
            sakoe_chiba_radius=sakoe_chiba_radius,
        )
        labels = model.fit_predict(X)
        inertias.append(float(model.inertia_))
        if len(set(labels)) > 1:
            silhouettes.append(
                float(silhouette_score(X, labels, metric=metric, random_state=random_state))
            )
        else:
            silhouettes.append(float("nan"))

    # Elbow via kneed on the inertia curve (convex, decreasing).
    elbow_k: Optional[int] = None
    try:
        from kneed import KneeLocator

        kl = KneeLocator(k_values, inertias, curve="convex", direction="decreasing")
        elbow_k = int(kl.elbow) if kl.elbow is not None else None
    except Exception:
        elbow_k = None

    # Best silhouette (ignore NaN single-cluster degenerate cases).
    sil_arr = np.array(silhouettes, dtype=float)
    silhouette_k: Optional[int] = None
    if not np.all(np.isnan(sil_arr)):
        silhouette_k = int(k_values[int(np.nanargmax(sil_arr))])

    candidates = [k for k in (elbow_k, silhouette_k) if k is not None]
    suggested_k = int(max(candidates)) if candidates else k_values[0]

    return {
        "k_values": k_values,
        "inertias": inertias,
        "silhouettes": silhouettes,
        "elbow_k": elbow_k,
        "silhouette_k": silhouette_k,
        "suggested_k": suggested_k,
    }


# ---------------------------------------------------------------------------
# 5. Fit DTW clustering
# ---------------------------------------------------------------------------
def fit_dtw_clusters(
    X: np.ndarray,
    ids: Sequence,
    n_clusters: int,
    unique_id: str = "unique_id",
    metric: str = DEFAULT_METRIC,
    random_state: int = DEFAULT_RANDOM_STATE,
    sakoe_chiba_radius: Optional[int] = None,
    max_iter: int = 50,
    n_init: int = 3,
) -> Tuple[pd.DataFrame, object]:
    """Fit DTW ``TimeSeriesKMeans`` and return per-series cluster labels.

    Parameters
    ----------
    X
        ``(n_series, n_timestamps, 1)`` array from :func:`build_series_matrix`.
    ids
        Series ids aligned to ``X`` rows (second element of ``build_series_matrix``).
    n_clusters
        Chosen ``k`` (e.g. ``choose_n_clusters(...)['suggested_k']``).
    unique_id
        Name for the id column in the returned frame.
    metric, random_state, sakoe_chiba_radius, max_iter, n_init
        Passed through to :func:`build_dtw_model`.

    Returns
    -------
    (labels_df, model)
        ``labels_df`` : DataFrame ``[unique_id, cluster]`` (cluster as ``int``).
        ``model``     : the fitted ``TimeSeriesKMeans`` (exposes ``cluster_centers_``).
    """
    model = build_dtw_model(
        n_clusters=n_clusters,
        metric=metric,
        max_iter=max_iter,
        n_init=n_init,
        random_state=random_state,
        sakoe_chiba_radius=sakoe_chiba_radius,
    )
    labels = model.fit_predict(X)
    labels_df = pd.DataFrame({unique_id: list(ids), "cluster": labels.astype(int)})
    return labels_df, model


# ---------------------------------------------------------------------------
# 6. Merge labels back to profiling -> profile_cluster (NB04 output contract)
# ---------------------------------------------------------------------------
def assign_profile_cluster(
    df_profiling: pd.DataFrame,
    labels_df: pd.DataFrame,
    unique_id: str,
    profile_col: str = "profile",
    regular_label: str = "regular",
) -> pd.DataFrame:
    """Merge DTW cluster ids into a ``profile_cluster`` column (notebook 04 output).

    Regular series receive their cluster id; every other profile keeps its
    original label. The result matches the schema notebook 05 (Feature
    Engineering) expects downstream.

    Parameters
    ----------
    df_profiling
        Profiling table with one row per ``unique_id`` and a ``profile`` column.
    labels_df
        ``[unique_id, cluster]`` from :func:`fit_dtw_clusters`.
    unique_id
        Series id column.
    profile_col
        Profile label column in ``df_profiling``. Default ``"profile"``.
    regular_label
        Value marking regular series. Default ``"regular"``.

    Returns
    -------
    pd.DataFrame
        ``df_profiling`` with ``profile``/``cluster`` replaced by a single string
        ``profile_cluster`` column.
    """
    out = pd.merge(df_profiling, labels_df, on=unique_id, how="left", validate="1:1")

    out["profile_cluster"] = out[profile_col].astype(str)
    is_regular = out[profile_col] == regular_label
    out.loc[is_regular, "profile_cluster"] = out.loc[is_regular, "cluster"].astype("Int64").astype(str)

    out = out.drop(columns=[c for c in (profile_col, "cluster") if c in out.columns])
    out["profile_cluster"] = out["profile_cluster"].astype(str)
    return out


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------
def cluster_summary(labels_df: pd.DataFrame, unique_id: str = "unique_id") -> pd.DataFrame:
    """Return the number of series per DTW cluster."""
    return (
        labels_df.groupby("cluster")[unique_id]
        .nunique()
        .rename("n_series")
        .reset_index()
        .sort_values("cluster")
        .reset_index(drop=True)
    )


def narrate_clusters(
    labels_df: pd.DataFrame,
    diagnostics: Optional[Dict[str, object]] = None,
    metric: str = DEFAULT_METRIC,
    unique_id: str = "unique_id",
) -> str:
    """Produce a short plain-language summary of the DTW clustering result."""
    summary = cluster_summary(labels_df, unique_id=unique_id)
    n_series = int(summary["n_series"].sum())
    n_clusters = int(summary["cluster"].nunique())

    lines = [
        f"DTW clustering ({metric}) grouped {n_series} regular series into "
        f"{n_clusters} clusters by shape (phase-shift tolerant).",
    ]
    if diagnostics is not None:
        lines.append(
            "Suggested k = {suggested} (elbow k = {elbow}, silhouette k = {sil}).".format(
                suggested=diagnostics.get("suggested_k"),
                elbow=diagnostics.get("elbow_k"),
                sil=diagnostics.get("silhouette_k"),
            )
        )
    sizes = ", ".join(
        f"cluster {int(r.cluster)}: {int(r.n_series)}" for r in summary.itertuples()
    )
    lines.append(f"Cluster sizes — {sizes}.")
    return " ".join(lines)
