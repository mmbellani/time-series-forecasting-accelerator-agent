# 01 · Data Preparation

**Notebook:** `src/notebooks/01 DataPreparation.ipynb`
**Reads:** raw panel data · **Writes:** `<scenario>_prepared`

## Purpose

Turn raw input into a clean, gap-free panel ready for analysis and modelling. This is the foundation every downstream stage depends on.

## What it does

1. **Understand the structure** — determine whether the data is cross-sectional or panel (one row per series per date).
2. **Build a full time sequence** — create a complete date spine per series at the target frequency (e.g. weekly `W`, monthly `MS`) so there are no implicit gaps.
3. **Handle missing values** — fill or flag gaps introduced by the full-sequence build.

## Key parameters

Configured at the top of the notebook:

- `date_var`, `date_format` — date column and parse format
- `unique_id` / `id` — series identifier(s)
- `y` — target variable
- `frequency` — series frequency (`D`, `W`, `MS`, …)
- Lakehouse/table names for input and output

## Output

`<scenario>_prepared` — a dense panel with a complete date spine per series and missing values resolved. Consumed by [02 EDA](02-Exploratory-Data-Analysis) and [03 Profiling](03-Profiling-Intermittent).

## Next

→ [02 · Exploratory Data Analysis](02-Exploratory-Data-Analysis)
