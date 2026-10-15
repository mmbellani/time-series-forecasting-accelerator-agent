"""Champion / challenger drift gate with a registry and a decision log (storage-agnostic).

Every scheduled run REFITS the frozen recipe and scores it on the current walk-forward
folds. A gate decides what happens next:

* no champion            -> bootstrap: the refit becomes the first champion;
* champion exists        -> accept while ``candidate_wmape - champion_wmape <= sigma * std``
                            (one-sided: improvements always pass; the band is a bootstrap
                            estimate of WMAPE noise, so real deterioration is told from
                            sampling wobble without hand-tuned thresholds);
* drift or staleness     -> tuning produces a CHALLENGER; it is promoted only if it passes
                            the same band against the champion, otherwise the champion is
                            kept and a human-review alert is logged.

Lessons encoded from the field review
-------------------------------------
* Compare apples to apples: re-score the champion's config on the CURRENT folds
  (``score_fn(champion_config)``) instead of trusting its stored score from an older window.
* Bootstrap the std at ROW level over the pooled (actual, pred) pairs - fold-level
  resampling with 2-3 folds rests the whole threshold on 2-3 numbers.
* Floor the band (``abs_min``) so a tiny stored std cannot trip tuning on every run.
* A passing refit must not be discarded when a forced / stale tune returns a worse
  challenger: fall back to promoting the refit.
* Scope the registry by model name so a new model bootstraps instead of inheriting a
  champion; write every verdict with the numbers behind it.

Storage: ``ParquetStore`` (local / lakehouse files) or ``SparkStore`` (Delta tables).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

REGISTRY_COLUMNS = ["model_name", "version", "run_stamp", "wmape", "wmape_std", "fold_scores", "config_json", "tuned", "role",
                    "is_champion", "created_at"]
LOG_COLUMNS = ["model_name", "run_stamp", "gate", "verdict", "candidate_wmape", "champion_wmape", "std", "threshold", "detail", "created_at"]


# ---------------------------------------------------------------------------
# storage back-ends
# ---------------------------------------------------------------------------
class ParquetStore:
    """Append-only tables as parquet files in a folder (local or mounted lakehouse path)."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    def read(self, name: str, columns: Sequence[str]) -> pd.DataFrame:
        p = self.folder / f"{name}.parquet"
        return pd.read_parquet(p) if p.exists() else pd.DataFrame(columns=list(columns))

    def append(self, name: str, row: dict, columns: Sequence[str]) -> None:
        df = pd.concat([self.read(name, columns), pd.DataFrame([row])], ignore_index=True)
        df.to_parquet(self.folder / f"{name}.parquet", index=False)

    def update(self, name: str, mask_fn: Callable[[pd.DataFrame], pd.Series], col: str, value, columns: Sequence[str]) -> None:
        df = self.read(name, columns)
        if len(df):
            df.loc[mask_fn(df), col] = value
            df.to_parquet(self.folder / f"{name}.parquet", index=False)


class SparkStore:
    """Delta tables via an active SparkSession (``spark``)."""

    def __init__(self, spark, prefix: str):
        self.spark, self.prefix = spark, prefix

    def _t(self, name):
        return f"{self.prefix}{name}"

    def read(self, name, columns):
        try:
            return self.spark.table(self._t(name)).toPandas()
        except Exception:
            return pd.DataFrame(columns=list(columns))

    def append(self, name, row, columns):
        self.spark.createDataFrame(pd.DataFrame([row])).write.mode("append").option("mergeSchema", "true").saveAsTable(self._t(name))

    def update(self, name, mask_fn, col, value, columns):
        df = self.read(name, columns)
        if len(df):
            df.loc[mask_fn(df), col] = value
            self.spark.createDataFrame(df).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(self._t(name))


# ---------------------------------------------------------------------------
# registry + log
# ---------------------------------------------------------------------------
@dataclass
class Registry:
    store: object
    model_name: str
    run_stamp: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))

    def champion(self) -> Optional[dict]:
        df = self.store.read("model_registry", REGISTRY_COLUMNS)
        df = df[(df["model_name"] == self.model_name) & (df["is_champion"] == True)]  # noqa: E712
        if df.empty:
            return None
        r = df.sort_values("created_at").iloc[-1]
        return {"version": r["version"], "wmape": float(r["wmape"]), "wmape_std": float(r["wmape_std"]),
                "config": json.loads(r["config_json"]) if r["config_json"] else None, "created_at": r["created_at"]}

    def last_tuned_at(self) -> Optional[pd.Timestamp]:
        df = self.store.read("model_registry", REGISTRY_COLUMNS)
        df = df[(df["model_name"] == self.model_name) & (df["tuned"] == True)]  # noqa: E712
        return pd.Timestamp(df["created_at"].max()) if len(df) else None

    def next_version(self) -> str:
        df = self.store.read("model_registry", REGISTRY_COLUMNS)
        df = df[df["model_name"] == self.model_name]
        nums = df["version"].astype(str).str.extract(r"v(\d+)")[0].dropna().astype(int) if len(df) else pd.Series(dtype=int)
        return f"v{(int(nums.max()) if len(nums) else 0) + 1}"

    def register(self, version: str, wmape: float, std: float, fold_scores: Sequence[float], config: dict, tuned: bool, role: str,
                 is_champion: bool) -> None:
        if is_champion:
            self.store.update("model_registry", lambda d: (d["model_name"] == self.model_name) & (d["is_champion"] == True), "is_champion", False,  # noqa: E712
                              REGISTRY_COLUMNS)
        self.store.append("model_registry", {"model_name": self.model_name, "version": version, "run_stamp": self.run_stamp, "wmape": float(wmape),
                                             "wmape_std": float(std), "fold_scores": json.dumps([float(x) for x in fold_scores]),
                                             "config_json": json.dumps(config, default=str), "tuned": bool(tuned), "role": role,
                                             "is_champion": bool(is_champion), "created_at": datetime.now()}, REGISTRY_COLUMNS)

    def decide(self, gate: str, verdict: str, cand: Optional[float], champ: Optional[float], std: Optional[float], threshold: Optional[float],
               detail: str) -> None:
        self.store.append("decision_log", {"model_name": self.model_name, "run_stamp": self.run_stamp, "gate": gate, "verdict": verdict,
                                           "candidate_wmape": cand, "champion_wmape": champ, "std": std, "threshold": threshold,
                                           "detail": detail, "created_at": datetime.now()}, LOG_COLUMNS)

    def decisions(self) -> pd.DataFrame:
        df = self.store.read("decision_log", LOG_COLUMNS)
        return df[df["model_name"] == self.model_name].sort_values("created_at")


# ---------------------------------------------------------------------------
# statistics + gate
# ---------------------------------------------------------------------------
def wmape(a, p) -> float:
    a, p = np.asarray(a, float), np.asarray(p, float)
    d = np.abs(a).sum()
    return np.nan if d == 0 else float(100.0 * np.abs(a - p).sum() / d)


def bootstrap_wmape_std(actual, pred, n_boot=300, random_state=42) -> float:
    """Row-level bootstrap of the pooled WMAPE - the noise band the gate uses."""
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    m = ~np.isnan(a) & ~np.isnan(p)
    a, p = a[m], p[m]
    if len(a) < 5:
        return 0.0
    rng = np.random.default_rng(random_state)
    idx = rng.integers(0, len(a), size=(n_boot, len(a)))
    boots = [wmape(a[i], p[i]) for i in idx]
    return float(np.nanstd(boots))


def drift_gate(candidate_wmape: float, champion_wmape: float, champion_std: float, candidate_std: float, sigma=2.0, abs_min=0.5) -> dict:
    """One-sided band: accept while deterioration <= sigma * max(champion_std, candidate_std, abs_min)."""
    band = max(float(champion_std or 0.0), float(candidate_std or 0.0), abs_min)
    threshold = sigma * band
    deterioration = candidate_wmape - champion_wmape
    return {"accept": bool(deterioration <= threshold), "deterioration": float(deterioration), "threshold": float(threshold), "std": band,
            "detail": f"deterioration={deterioration:+.3f} vs {sigma}*std={threshold:.3f} (std band {band:.3f})"}


def staleness_trigger(last_tuned_at: Optional[pd.Timestamp], stale_months=6, now: Optional[pd.Timestamp] = None) -> Tuple[bool, float]:
    if last_tuned_at is None:
        return False, np.nan
    months = (pd.Timestamp(now or pd.Timestamp.now()) - pd.Timestamp(last_tuned_at)).days / 30.0
    return months > stale_months, months


def run_cycle(registry: Registry, committed_config: dict, score_fn: Callable[[dict], Tuple[float, Sequence[float], np.ndarray, np.ndarray]],
              tune_fn: Optional[Callable[[], dict]] = None, force_tuning=False, sigma=2.0, abs_min=0.5, stale_months=6,
              min_scored_rows=50) -> dict:
    """One scheduled cycle: refit gate -> (tuning) -> challenger gate -> registry write. Returns the summary.

    ``score_fn(config)`` must return (wmape, per_fold_wmapes, actual_array, pred_array) on the CURRENT folds.
    ``tune_fn()`` returns a challenger config.
    """
    champ = registry.champion()
    refit_w, refit_folds, a, p = score_fn(committed_config)
    refit_std = bootstrap_wmape_std(a, p)
    out = {"run_stamp": registry.run_stamp, "refit_wmape": refit_w, "refit_std": refit_std, "n_scored_rows": int(len(a)), "need_tuning": force_tuning}
    if len(a) < min_scored_rows:
        registry.decide("coverage", "INSUFFICIENT_ROWS", refit_w, champ["wmape"] if champ else None, refit_std, None,
                        f"only {len(a)} scored rows (< {min_scored_rows}); no promotion this run")
        out.update(promote=False, role="refit", alert=True, verdict="INSUFFICIENT_ROWS")
        return out

    if champ is None:
        registry.decide("refit_gate", "BOOTSTRAP_CHAMPION", refit_w, None, refit_std, None, "no champion - refit becomes the first champion")
        promote_refit, champ_now = True, None
    else:
        # apples to apples: re-score the champion config on the current folds
        champ_w, _, ca, cp = score_fn(champ["config"]) if champ.get("config") else (champ["wmape"], None, a, p)
        champ_std = bootstrap_wmape_std(ca, cp) if champ.get("config") else champ["wmape_std"]
        g = drift_gate(refit_w, champ_w, champ_std, refit_std, sigma, abs_min)
        champ_now = {**champ, "wmape_now": champ_w, "std_now": champ_std}
        registry.decide("refit_gate", "ACCEPT_REFIT" if g["accept"] else "DRIFT_DETECTED", refit_w, champ_w, g["std"], g["threshold"], g["detail"])
        promote_refit = g["accept"]
        out["need_tuning"] = out["need_tuning"] or not g["accept"]
        out["champion_wmape_now"] = champ_w

    stale, months = staleness_trigger(registry.last_tuned_at(), stale_months)
    if stale:
        out["need_tuning"] = True
        registry.decide("staleness", "TUNE_DUE", refit_w, None, None, None, f"{months:.1f} months since the last tune > {stale_months}")

    final = {"config": committed_config, "wmape": refit_w, "std": refit_std, "folds": refit_folds, "tuned": False, "role": "refit"}
    promote, alert = promote_refit, False
    if out["need_tuning"] and tune_fn is not None:
        ch_cfg = tune_fn()
        ch_w, ch_folds, ca, cp = score_fn(ch_cfg)
        ch_std = bootstrap_wmape_std(ca, cp)
        ref_w = champ_now["wmape_now"] if champ_now else refit_w
        ref_std = champ_now["std_now"] if champ_now else refit_std
        g = drift_gate(ch_w, ref_w, ref_std, ch_std, sigma, abs_min)
        better_than_refit = ch_w <= refit_w + 1e-9          # a challenger must at least beat the refit it was meant to improve
        if g["accept"] and better_than_refit:
            registry.decide("challenger_gate", "PROMOTE_CHALLENGER", ch_w, ref_w, g["std"], g["threshold"], g["detail"])
            final, promote = {"config": ch_cfg, "wmape": ch_w, "std": ch_std, "folds": ch_folds, "tuned": True, "role": "challenger"}, True
        else:
            # the challenger is worse: keep the refit if it passed, otherwise keep the champion and alert
            registry.decide("challenger_gate", "CHALLENGER_REJECTED", ch_w, ref_w, g["std"], g["threshold"],
                            g["detail"] + ("; refit promoted instead" if promote_refit else "; champion retained - human review"))
            alert = not promote_refit
    version = registry.next_version()
    if promote:
        registry.register(version, final["wmape"], final["std"], final["folds"], final["config"], final["tuned"], final["role"], True)
    else:
        registry.register(f"{version}_candidate", final["wmape"], final["std"], final["folds"], final["config"], final["tuned"], final["role"], False)
    out.update(promote=promote, role=final["role"], tuned=final["tuned"], final_wmape=final["wmape"], version=version if promote else None, alert=alert)
    return out


def model_card(summary: dict, committed: Dict[str, dict], metrics_table: Optional[pd.DataFrame] = None, title="Model card") -> str:
    lines = [f"# {title} ({summary.get('run_stamp')})", "",
             f"- refit WMAPE **{summary.get('refit_wmape', float('nan')):.2f}** (std {summary.get('refit_std', float('nan')):.2f}) on {summary.get('n_scored_rows')} scored rows",
             f"- champion re-scored on current folds: {summary.get('champion_wmape_now', 'n/a')}",
             f"- promoted: **{summary.get('promote')}** as {summary.get('role')} {summary.get('version') or ''} | tuned this run: {summary.get('tuned')} | alert: {summary.get('alert')}",
             "", "## Per-cluster recipe", "", "| cluster | method | blend | rules |", "| --- | --- | --- | --- |"]
    for cl, cfg in committed.items():
        b, r = cfg.get("blend"), cfg.get("rules")
        bs = "-" if not b else f"{b['w']:.2f}*q{int(b['q_lo'] * 100)} + {1 - b['w']:.2f}*q{int(b['q_hi'] * 100)}"
        rs = "-" if not r else f"up > {r['up_margin']:.0%} -> q{int(r['q_hi_rule'] * 100)}; qty <= -{r['down_margin']:.0%} -> q{int(r['q_lo_rule'] * 100)}"
        lines.append(f"| {cl} | {cfg.get('method')} | {bs} | {rs} |")
    if metrics_table is not None and len(metrics_table):
        lines += ["", "## Accuracy", "", "| " + " | ".join(metrics_table.columns) + " |", "| " + " | ".join("---" for _ in metrics_table.columns) + " |"]
        for _, r in metrics_table.round(2).iterrows():
            lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r.values) + " |")
    return "\n".join(lines)
