"""Forecast explainability utilities.

Explain time-series forecast results and analyze the feature weights that drive a
trained forecasting model. Built for the Time Series Forecasting Accelerator pipeline
(LightGBM + mlforecast, notebooks 05 and 06), but works with any LightGBM booster,
``LGBMRegressor`` estimator, or scikit-learn estimator exposing ``feature_importances_``.

Public API
----------
- ``classify_feature`` / ``feature_family_map`` : map feature names to families.
- ``feature_importance``       : tidy global importance (gain + split), grouped by family.
- ``family_importance``        : importance aggregated by feature family.
- ``importance_by_cluster``    : global importance for each per-cluster model.
- ``explain_prediction``       : additive per-feature contributions for one forecast point.
- ``narrate_importance``       : plain-language summary of global drivers.
- ``narrate_prediction``       : plain-language summary of a single forecast.

The module has no hard dependency on ``shap``. When ``shap`` is unavailable, single-point
explanations fall back to LightGBM's built-in ``pred_contrib`` (SHAP values for tree models).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Feature family classification
# ---------------------------------------------------------------------------

# Ordered rules: the first matching pattern wins.
_FAMILY_RULES: List[tuple] = [
    ("rolling", re.compile(r"rolling|roll_|_mean_|_std_|expanding", re.IGNORECASE)),
    ("lag", re.compile(r"(^|_)lag\d*|lag_\d+", re.IGNORECASE)),
    ("calendar", re.compile(r"^(year|month|week|quarter|day|dayofweek|dayofyear|weekofyear|is_weekend|is_month_end|is_month_start)$", re.IGNORECASE)),
    ("exog", re.compile(r"promo|holiday|price|discount|weather|event|campaign", re.IGNORECASE)),
]


def classify_feature(name: str, static_features: Optional[Sequence[str]] = None,
                     categorical_features: Optional[Sequence[str]] = None) -> str:
    """Return the feature family for a single feature name.

    Families: ``lag``, ``rolling``, ``calendar``, ``exog``, ``static``, ``categorical``,
    or ``other``. Explicit ``static_features`` / ``categorical_features`` take precedence
    over pattern matching.
    """
    if static_features and name in set(static_features):
        return "static"
    if categorical_features and name in set(categorical_features):
        return "categorical"
    for family, pattern in _FAMILY_RULES:
        if pattern.search(name):
            return family
    return "other"


def feature_family_map(feature_cols: Sequence[str],
                       static_features: Optional[Sequence[str]] = None,
                       categorical_features: Optional[Sequence[str]] = None) -> Dict[str, str]:
    """Map every feature name to its family."""
    return {
        c: classify_feature(c, static_features, categorical_features)
        for c in feature_cols
    }


# ---------------------------------------------------------------------------
# Model introspection helpers
# ---------------------------------------------------------------------------

def _get_booster(model):
    """Return the underlying LightGBM ``Booster`` from a variety of wrappers.

    Accepts a ``lightgbm.Booster``, a ``LGBMRegressor``/``LGBMClassifier`` (via
    ``.booster_``), or an mlforecast-wrapped model. Returns ``None`` if no booster
    is available (e.g. a generic scikit-learn estimator).
    """
    # Raw booster already exposes feature_importance()
    if hasattr(model, "feature_importance") and hasattr(model, "num_trees"):
        return model
    if hasattr(model, "booster_"):
        return model.booster_
    # mlforecast may store the estimator directly; try common attribute
    inner = getattr(model, "model", None)
    if inner is not None and hasattr(inner, "booster_"):
        return inner.booster_
    return None


def _raw_importances(model, feature_cols: Sequence[str]) -> pd.DataFrame:
    """Extract gain and split importances, robust to model type."""
    booster = _get_booster(model)
    if booster is not None:
        gain = np.asarray(booster.feature_importance(importance_type="gain"), dtype=float)
        split = np.asarray(booster.feature_importance(importance_type="split"), dtype=float)
        names = list(booster.feature_name())
    elif hasattr(model, "feature_importances_"):
        # Generic sklearn estimator: only one importance vector available.
        gain = np.asarray(model.feature_importances_, dtype=float)
        split = gain.copy()
        names = list(getattr(model, "feature_name_", feature_cols))
    else:
        raise TypeError(
            "Unsupported model type: expected a LightGBM booster/estimator or an "
            "estimator exposing `feature_importances_`."
        )

    # Align to provided feature_cols when lengths match; otherwise trust model names.
    if len(names) == len(feature_cols) and set(names) != set(feature_cols):
        # Booster used generic names (Column_0, ...); prefer caller's names positionally.
        names = list(feature_cols)
    return pd.DataFrame({"feature": names, "gain": gain, "split": split})


def _pct(series: pd.Series) -> pd.Series:
    total = series.sum()
    if total <= 0:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return series / total * 100.0


# ---------------------------------------------------------------------------
# Global importance
# ---------------------------------------------------------------------------

def feature_importance(model, feature_cols: Sequence[str],
                       static_features: Optional[Sequence[str]] = None,
                       categorical_features: Optional[Sequence[str]] = None,
                       normalize: bool = True) -> pd.DataFrame:
    """Compute tidy global feature importance for a trained model.

    Parameters
    ----------
    model
        A LightGBM ``Booster``, ``LGBMRegressor``, or sklearn estimator with
        ``feature_importances_``.
    feature_cols
        The feature columns used to train the model (same order as training).
    static_features, categorical_features
        Optional explicit family assignments.
    normalize
        When ``True`` (default) add ``gain_pct`` / ``split_pct`` columns.

    Returns
    -------
    pandas.DataFrame
        Columns: ``feature``, ``family``, ``gain``, ``split``[, ``gain_pct``,
        ``split_pct``], sorted by gain descending.
    """
    imp = _raw_importances(model, feature_cols)
    fam = feature_family_map(imp["feature"], static_features, categorical_features)
    imp["family"] = imp["feature"].map(fam)
    if normalize:
        imp["gain_pct"] = _pct(imp["gain"]).round(2)
        imp["split_pct"] = _pct(imp["split"]).round(2)
    imp = imp.sort_values("gain", ascending=False).reset_index(drop=True)
    cols = ["feature", "family", "gain", "split"]
    if normalize:
        cols += ["gain_pct", "split_pct"]
    return imp[cols]


def family_importance(importance_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate an importance DataFrame (from :func:`feature_importance`) by family."""
    value_cols = [c for c in ["gain", "split", "gain_pct", "split_pct"] if c in importance_df.columns]
    grouped = (
        importance_df.groupby("family", as_index=False)[value_cols]
        .sum()
        .sort_values("gain", ascending=False)
        .reset_index(drop=True)
    )
    grouped["n_features"] = (
        importance_df.groupby("family")["feature"].count().reindex(grouped["family"]).values
    )
    return grouped


def importance_by_cluster(cluster_models: Mapping,
                          feature_cols: Sequence[str],
                          static_features: Optional[Sequence[str]] = None,
                          categorical_features: Optional[Sequence[str]] = None,
                          top_n: Optional[int] = None) -> pd.DataFrame:
    """Compute global importance for each per-cluster model.

    Parameters
    ----------
    cluster_models
        Mapping of ``cluster_id -> trained model``.
    top_n
        If given, keep only the top ``n`` features (by gain) per cluster.

    Returns
    -------
    pandas.DataFrame
        Long format with a ``cluster`` column plus the columns from
        :func:`feature_importance`.
    """
    frames = []
    for cid, mdl in cluster_models.items():
        try:
            fi = feature_importance(mdl, feature_cols, static_features, categorical_features)
        except TypeError:
            continue
        if top_n is not None:
            fi = fi.head(top_n)
        fi.insert(0, "cluster", cid)
        frames.append(fi)
    if not frames:
        return pd.DataFrame(columns=["cluster", "feature", "family", "gain", "split"])
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Single-prediction explanation (SHAP / pred_contrib)
# ---------------------------------------------------------------------------

@dataclass
class PredictionExplanation:
    """Additive decomposition of a single forecast point."""

    prediction: float
    baseline: float
    contributions: pd.DataFrame  # columns: feature, family, contribution, abs_contribution
    method: str = "pred_contrib"
    meta: Dict = field(default_factory=dict)

    def top(self, n: int = 5, direction: Optional[str] = None) -> pd.DataFrame:
        """Return the ``n`` largest contributions.

        ``direction`` may be ``"up"`` (positive), ``"down"`` (negative), or ``None``
        (by absolute magnitude).
        """
        df = self.contributions
        if direction == "up":
            df = df[df["contribution"] > 0].sort_values("contribution", ascending=False)
        elif direction == "down":
            df = df[df["contribution"] < 0].sort_values("contribution")
        else:
            df = df.sort_values("abs_contribution", ascending=False)
        return df.head(n).reset_index(drop=True)


def _shap_values(model, X: pd.DataFrame):
    """Return (shap_matrix, base_value) using shap if available, else pred_contrib."""
    try:
        import shap  # type: ignore

        explainer = shap.TreeExplainer(model)
        sv = explainer.shap_values(X)
        base = explainer.expected_value
        if isinstance(base, (list, np.ndarray)):
            base = float(np.ravel(base)[0])
        return np.asarray(sv), float(base), "shap"
    except Exception:
        pass

    # Fallback: LightGBM pred_contrib returns [contribs..., base] per row.
    booster = _get_booster(model)
    if booster is None:
        raise TypeError(
            "explain_prediction requires shap or a LightGBM model exposing pred_contrib."
        )
    contrib = booster.predict(np.asarray(X), pred_contrib=True)
    contrib = np.asarray(contrib)
    base = float(contrib[0, -1])
    return contrib[:, :-1], base, "pred_contrib"


def explain_prediction(model, X_row: pd.DataFrame, feature_cols: Sequence[str],
                       static_features: Optional[Sequence[str]] = None,
                       categorical_features: Optional[Sequence[str]] = None) -> PredictionExplanation:
    """Explain a single forecast point as additive feature contributions.

    Parameters
    ----------
    model
        A LightGBM model (booster or estimator).
    X_row
        A single-row DataFrame with the training feature columns.
    feature_cols
        Feature columns (used for family classification and ordering).

    Returns
    -------
    PredictionExplanation
        Baseline + per-feature contributions that sum to the prediction.
    """
    if len(X_row) != 1:
        raise ValueError(f"X_row must contain exactly one row, got {len(X_row)}.")

    X = X_row[list(feature_cols)] if set(feature_cols).issubset(X_row.columns) else X_row
    sv, base, method = _shap_values(model, X)
    contribs = np.ravel(sv[0])

    fam = feature_family_map(feature_cols, static_features, categorical_features)
    df = pd.DataFrame({
        "feature": list(feature_cols),
        "family": [fam.get(c, "other") for c in feature_cols],
        "value": np.ravel(X.iloc[0].values),
        "contribution": contribs,
    })
    df["abs_contribution"] = df["contribution"].abs()
    df = df.sort_values("abs_contribution", ascending=False).reset_index(drop=True)

    prediction = float(base + contribs.sum())
    return PredictionExplanation(
        prediction=prediction,
        baseline=float(base),
        contributions=df,
        method=method,
    )


# ---------------------------------------------------------------------------
# Narrative generation
# ---------------------------------------------------------------------------

_FAMILY_PHRASE = {
    "lag": "recent history (autocorrelation)",
    "rolling": "short-term trend and volatility",
    "calendar": "seasonality and time-of-year effects",
    "static": "series-level attributes",
    "categorical": "group membership",
    "exog": "external drivers",
    "other": "other features",
}


def narrate_importance(importance_df: pd.DataFrame, top_n: int = 8) -> str:
    """Produce a plain-language summary of global feature drivers."""
    if importance_df.empty:
        return "No feature importances available for this model."

    pct_col = "gain_pct" if "gain_pct" in importance_df.columns else None
    top = importance_df.head(top_n)
    fam = family_importance(importance_df)

    lines: List[str] = []
    lead_family = fam.iloc[0]["family"]
    lead_share = fam.iloc[0].get("gain_pct")
    share_txt = f" (~{lead_share:.0f}% of total gain)" if lead_share is not None else ""
    lines.append(
        f"The model is driven mainly by **{_FAMILY_PHRASE.get(lead_family, lead_family)}**"
        f"{share_txt}."
    )

    lines.append("")
    lines.append(f"Top {len(top)} features by gain:")
    for _, r in top.iterrows():
        share = f" — {r[pct_col]:.1f}% of gain" if pct_col else ""
        lines.append(f"- `{r['feature']}` [{r['family']}]{share}")

    lines.append("")
    lines.append("Contribution by feature family:")
    for _, r in fam.iterrows():
        share = f" ({r['gain_pct']:.1f}%)" if "gain_pct" in fam.columns else ""
        lines.append(f"- {r['family']}: {int(r['n_features'])} feature(s){share}")

    return "\n".join(lines)


def narrate_prediction(explanation: PredictionExplanation, top_n: int = 5,
                       unit: str = "") -> str:
    """Produce a plain-language explanation of a single forecast point."""
    exp = explanation
    u = f" {unit}".rstrip()

    def fmt(v: float) -> str:
        return f"{v:,.2f}{u}"

    lines = [
        f"Forecast value: **{fmt(exp.prediction)}** "
        f"(baseline {fmt(exp.baseline)}, method: {exp.method}).",
        "",
    ]

    ups = exp.top(top_n, direction="up")
    downs = exp.top(top_n, direction="down")

    if not ups.empty:
        lines.append("Pushing the forecast **up**:")
        for _, r in ups.iterrows():
            lines.append(
                f"- `{r['feature']}` = {r['value']:.4g} [{r['family']}] "
                f"→ +{r['contribution']:,.2f}"
            )
        lines.append("")

    if not downs.empty:
        lines.append("Pushing the forecast **down**:")
        for _, r in downs.iterrows():
            lines.append(
                f"- `{r['feature']}` = {r['value']:.4g} [{r['family']}] "
                f"→ {r['contribution']:,.2f}"
            )

    return "\n".join(lines).rstrip()
