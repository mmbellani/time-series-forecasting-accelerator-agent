# Error Analysis

**Category:** Diagnostics · **Location:** `.github/skills/` · **Extra dependency:** none beyond `requirements.txt`

## What it does

Shows **where and when the forecast is wrong**, e.g. errors broken down by calendar.

## When to use it

After explainability, to find systematic patterns in errors (specific periods, series or clusters).

```mermaid
flowchart LR
    A[Forecast Explainability] --> B[Error Analysis] --> C[Hierarchical Reconciliation]
    style B stroke-width:3px
```

## Inputs & outputs

| | |
|---|---|
| **Reads** | Pipeline outputs: `profile_cluster` and/or `<scenario>_forecasts` |
| **Writes** | Its own results — the core notebooks are never modified |

!!! note
    See the skill's `SKILL.md` in `.github/skills/` for parameters and usage.

[:octicons-arrow-left-24: Back to Skills Overview](index.md)
