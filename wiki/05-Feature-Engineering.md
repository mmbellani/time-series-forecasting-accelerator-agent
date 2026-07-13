# 05 · Feature Engineering

**Notebook:** `src/notebooks/05 FeatureEngineering.ipynb`
**Reads:** `<scenario>_clustered` · **Writes:** `<scenario>_features`

## Purpose

Create the predictive features the LightGBM models consume, per `profile_cluster`.

## What it does

- **Lag features** — prior values at seasonality-aligned offsets.
- **Rolling statistics** — moving means/std over configurable windows.
- **Calendar features** — year, quarter, month, week, day-of-week, and related encodings.
- Optional **exogenous drivers** identified during [02 EDA](02-Exploratory-Data-Analysis) / [04 Clustering](04-Clustering) (e.g. promotions, holidays, weather).

Lag and window sizes should reflect the series frequency and seasonality (medium-risk customization).

## Output

`<scenario>_features` — the modelling table with engineered features and the `profile_cluster` grouping. Consumed by [06 Train / Tune](06-Train-Test-Select-Tune).

## Related skill

To understand which of these features actually drive predictions, see [Forecast Explainability](Skill-forecast-explainability).

## Next

→ [06 · Train / Test / Tune](06-Train-Test-Select-Tune)
