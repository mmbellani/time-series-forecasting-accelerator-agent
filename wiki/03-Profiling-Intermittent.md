# 03 · Profiling (Intermittent)

**Notebook:** `src/notebooks/03 ProfilingIntermittent.ipynb`
**Reads:** `<scenario>_prepared` · **Writes:** `<scenario>_profiled`

## Purpose

Classify each series by its demand pattern so the right modelling strategy can be applied. Regular/smooth series go on to clustering; intermittent and lumpy series are better served by dedicated methods (see the [Intermittent skill](Skill-forecasting-intermittent)).

## Classification

An **enhanced Syntetos–Boylan–Croston (SBC)** scheme based on three indicators:

- **CV²** — squared coefficient of variation of demand size
- **ADI** — Average Demand Interval
- **SDDI** — Standard Deviation of the Demand Interval

| Profile | Rule |
|---------|------|
| **Smooth / regular** | ADI < 1.32 and CV² < 0.49 |
| **Intermittent** | ADI ≥ 1.32 and CV² < 0.49 |
| **Erratic** | ADI < 1.32 and CV² ≥ 0.49 |
| **Lumpy** | ADI ≥ 1.32 and CV² ≥ 0.49 |
| **Unforecastable (time)** | SDDI ≥ threshold and CV² < 0.49 |
| **Unforecastable (quantity)** | SDDI ≥ threshold and CV² ≥ 0.49 |

## Output

`<scenario>_profiled` — the panel/series table with a `profile` column. Consumed by [04 Clustering](04-Clustering), which clusters only the `regular` series.

## Next

→ [04 · Clustering](04-Clustering)
