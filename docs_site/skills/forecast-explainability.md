# Forecast Explainability

**Category:** Diagnostics · **Location:** `.github/skills/` · **Extra dependency:** none beyond `requirements.txt`

## What it does

Explains **why the model produced a forecast**, using feature weights and SHAP values.

## When to use it

Building trust with stakeholders and checking that the model relies on sensible drivers. First step of the diagnostic flow.

```mermaid
flowchart LR
    A[Forecast Explainability] --> B[Error Analysis] --> C[Hierarchical Reconciliation]
    style A stroke-width:3px
```

## Inputs & outputs

| | |
|---|---|
| **Reads** | Pipeline outputs: `profile_cluster` and/or `<scenario>_forecasts` |
| **Writes** | Its own results — the core notebooks are never modified |

!!! note
    See the skill's `SKILL.md` in `.github/skills/` for parameters and usage.

[:octicons-arrow-left-24: Back to Skills Overview](index.md)
