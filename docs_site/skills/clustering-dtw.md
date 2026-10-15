# DTW Clustering

**Category:** Alternative clustering · **Location:** `.github/skills/` · **Extra dependency:** `tslearn>=0.6.3`

## What it does

Clusters regular series by **shape** using Dynamic Time Warping (DTW). It is a drop-in alternative to the Euclidean K-Means in [04 · Clustering](../pipeline/04-clustering.md) and keeps **the same output contract** (`profile_cluster`).

## When to use it

When series share similar patterns that are shifted or stretched in time — Euclidean distance would treat them as different, DTW aligns them.

```mermaid
flowchart LR
    A[Regular series] --> B[DTW distance] --> C[Clusters] --> D[profile_cluster]
```

## Inputs & outputs

| | |
|---|---|
| **Reads** | Pipeline outputs: `profile_cluster` and/or `<scenario>_forecasts` |
| **Writes** | Its own results — the core notebooks are never modified |

!!! note
    See the skill's `SKILL.md` in `.github/skills/` for parameters and usage.

[:octicons-arrow-left-24: Back to Skills Overview](index.md)
