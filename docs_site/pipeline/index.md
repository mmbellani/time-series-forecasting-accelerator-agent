# Pipeline Overview

```mermaid
flowchart TD
    R[(Source table)] --> N1[01 Data Preparation]
    N1 -->|clean panel| N2[02 EDA]
    N2 --> N3[03 Profiling]
    N3 -->|series profiles| N4[04 Clustering]
    N4 -->|profile_cluster| N5[05 Feature Engineering]
    N5 -->|feature table| N6[06 Train / Test / Tune]
    N6 --> O[(scenario_forecasts)]
```

| # | Notebook | Purpose |
|---|---|---|
| 01 | Data Preparation | Clean and standardise the panel |
| 02 | EDA | Understand trends, seasonality, gaps and outliers |
| 03 | Profiling | Flag intermittent and problematic series |
| 04 | Clustering | Group similar series for modelling |
| 05 | Feature Engineering | Lags, rolling stats, calendar effects |
| 06 | Train / Test / Select / Tune | Per-cluster LightGBM via `mlforecast`; writes `<scenario>_forecasts` |

Templates for the notebooks live in `src/notebooks/templates/`.

!!! info "Independently runnable stages"
    Each notebook reads the table produced by the prior stage and writes its own output table, so every stage can be run and inspected on its own.
