# Phase 3: Customization Planning

Generate a detailed customization plan for each notebook, specifying exactly what changes will be made with risk levels and rationale.

## Prerequisites

- Phase 2 completed: Scenario interpretation confirmed by user
- **Completion report** from Phase 2 (user provides path)

## Phase Start — Read Completion Report

At the start of this phase:
1. Read the completion report from the path provided by user
2. Extract Phase 1 + Phase 2 data for planning context
3. Use this context for customization planning

### Context from Prior Phases (via completion report):
  - scenario_name (derived folder name)
  - parameters (granularity, horizon, series structure, seasonality, etc.)
  - column_assignments (date, target, IDs, regressors)
  - notebook_config (per-notebook settings)
  - risk_assessment (change counts by risk level)
  - model_changes (any high-risk algorithm requests)

## Planning Process

1. **Read each template notebook** to understand current implementation
2. **Map parameters to specific cells** that need modification
3. **Classify each change** by risk level
4. **Document rationale** for every change
5. **Identify dependencies** between notebooks

## Template Notebook References

Read these notebooks to understand what to customize:

| Notebook | Path | Key Sections to Analyze |
|----------|------|-------------------------|
| 01 Data Prep | `src/notebooks/Fabric 01 DataPreparation.ipynb` | Table loading, date parsing, null handling, aggregation |
| 02 Exploratory Data Analysis | `src/notebooks/Fabric 02 ExploratoryDataAnalysis.ipynb` | Data exploration, summary statistics, visualizations |
| 03 Profiling | `src/notebooks/Fabric 03 ProfilingIntermittent.ipynb` | CV²/ADI calculation, classification thresholds, output tables |
| 04 Clustering | `src/notebooks/Fabric 04 Clustering.ipynb` | Feature scaling, K-Means params, cluster assignment |
| 05 Features | `src/notebooks/Fabric 05 FeatureEngineering.ipynb` | Lag creation, rolling stats, calendar features, regressor handling |
| 06 Train/Tune | `src/notebooks/Fabric 06 TrainTestSelectTune.ipynb` | Model definition, hyperparameters, Optuna config, metrics |

## Per-Notebook Planning

### Notebook 01: Data Preparation

**Key Customizations:**

| Change | Risk | Template Value | New Value | Rationale |
|--------|------|----------------|-----------|-----------|
| Input table name | Low | `<template_table>` | `<user_table>` | User's data source |
| Date column | Low | `<template_date_col>` | `<user_date_col>` | Column mapping |
| Target column | Low | `<template_target_col>` | `<user_target_col>` | Column mapping |
| ID columns | Low | `<template_id_cols>` | `<user_id_cols>` | Series grouping |
| Date parsing format | Low | `<template_format>` | `<inferred_format>` | Match data format |
| Aggregation logic | Medium | None or template | `<aggregation_code>` | If granularity change needed |
| Null handling strategy | Medium | Template default | `<strategy>` | Based on null profile |
| Output table name | Low | `<template_output>` | `<scenario>_prepared` | Consistent naming |

**Cells to Modify:**
- Cell X: Table loading — update table name
- Cell Y: Column definitions — update column names
- Cell Z: Date parsing — adjust format if needed
- Cell W: (Add new) Aggregation — if weekly/monthly aggregation needed

---

### Notebook 03: Profiling & Intermittent Classification

**Key Customizations:**

| Change | Risk | Template Value | New Value | Rationale |
|--------|------|----------------|-----------|-----------|
| Input table name | Low | `<template_table>` | `<scenario>_prepared` | Chain from Notebook 01 |
| CV² threshold | Medium | 0.49 | `<value>` | Tune based on data distribution |
| ADI threshold | Medium | 1.32 | `<value>` | Tune based on data distribution |
| Classification labels | Low | Template labels | Keep or customize | Domain terminology |
| Skip profiling | Medium | Enabled | Skip if single series | Simplify for simple cases |
| Output table name | Low | `<template_output>` | `<scenario>_profiled` | Consistent naming |

**Cells to Modify:**
- Cell X: Input table reference
- Cell Y: Threshold definitions
- Cell Z: (Optional) Skip logic if profiling not needed

---

### Notebook 04: Clustering

**Key Customizations:**

| Change | Risk | Template Value | New Value | Rationale |
|--------|------|----------------|-----------|----------|
| Enable/Skip clustering | Medium | Enabled | `<enabled/skip>` | Skip if series_count < 50 or single series |
| Input table name | Low | `<template_table>` | `<scenario>_profiled` | Chain from Notebook 03 |
| Number of clusters | Medium | Template default | `<n_clusters>` | Based on series count |
| Clustering features | Medium | Template features | `<feature_list>` | Adjust for domain |
| Clustering algorithm | High | K-Means | `<algorithm>` | If user requests different |
| Output table name | Low | `<template_output>` | `<scenario>_clustered` | Consistent naming |

**Cells to Modify:**
- Cell X: Input table reference
- Cell Y: Cluster count and parameters
- Cell Z: Feature selection for clustering
- Cell W: (If skipping) Add pass-through logic

**Skip Logic:**
If clustering is skipped, add a simple pass-through cell:
```python
# Clustering skipped — single series or low series count
df_clustered = df_profiled.withColumn("cluster_id", F.lit(0))
```

---

### Notebook 05: Feature Engineering

**Key Customizations:**

| Change | Risk | Template Value | New Value | Rationale |
|--------|------|----------------|-----------|----------|
| Input table name | Low | `<template_table>` | `<scenario>_clustered` | Chain from Notebook 04 |
| Lag features | Medium | Template lags | `<lag_list>` | Based on seasonality |
| Rolling window sizes | Medium | Template windows | `<window_list>` | Based on seasonality |
| Calendar features | Medium | Template features | `<feature_list>` | Domain-specific |
| Holiday calendar | Medium | None or default | `<holiday_config>` | If holidays mentioned |
| External regressors | High | None | `<regressor_cols>` | If user has regressors |
| Day-of-week features | Low | Template default | Enable/disable | Based on granularity |
| Month/quarter features | Low | Template default | Enable/disable | Based on granularity |
| Output table name | Low | `<template_output>` | `<scenario>_features` | Consistent naming |

**Cells to Modify:**
- Cell X: Input table reference
- Cell Y: Lag configuration
- Cell Z: Rolling window configuration
- Cell W: Calendar feature toggles
- Cell V: (Add new) External regressor integration if needed

**Lag Window Guidelines:**

| Seasonality | Recommended Lags |
|-------------|------------------|
| Daily + weekly pattern | [1, 7, 14, 21, 28] |
| Weekly + monthly pattern | [1, 4, 8, 12, 52] |
| Monthly + annual pattern | [1, 3, 6, 12] |

---

### Notebook 06: Train/Test/Select/Tune

**Key Customizations:**

| Change | Risk | Template Value | New Value | Rationale |
|--------|------|----------------|-----------|-----------|
| Input table name | Low | `<template_table>` | `<scenario>_features` | Chain from Notebook 05 |
| Forecast horizon | Low | Template horizon | `<horizon>` | User requirement |
| Train/test split | Low | Template ratio | `<split_ratio>` | Based on data size |
| Model selection | High | LightGBM | `<model_list>` | If user requests changes |
| Hyperparameter ranges | Medium | Template ranges | `<param_ranges>` | Tune for scenario |
| Optuna trials | Low | Template trials | `<n_trials>` | Based on compute budget |
| Evaluation metrics | Medium | Template metrics | `<metric_list>` | User preference |
| Cross-validation folds | Medium | Template folds | `<n_folds>` | Based on data size |
| Output table name | Low | `<template_output>` | `<scenario>_forecasts` | Consistent naming |
| Model save path | Low | Template path | `/lakehouse/default/Files/models/<scenario>/` | Organized storage |

**Cells to Modify:**
- Cell X: Input table and horizon
- Cell Y: Train/test split logic
- Cell Z: Model definition
- Cell W: Hyperparameter search space
- Cell V: Evaluation metrics
- Cell U: Output paths

---

## Checkpoint 3.1: Present Customization Plan

Present the complete plan for user approval:

```
📋 **Customization Plan**

**Scenario:** <scenario_name>
**Output Folder:** `.output/<scenario_name>_<YYYYMMDD>/`

---

### Change Summary

| Risk Level | Count | Description |
|------------|-------|-------------|
| 🟢 Low | <N> | Parameter substitutions (tables, columns, values) |
| 🟡 Medium | <N> | Structural changes (thresholds, features, logic flow) |
| 🔴 High | <N> | Algorithm/generative changes (models, new cells) |

---

### Notebook 01: Data Preparation

| # | Change | Risk | From → To |
|---|--------|------|-----------|
| 1 | Input table | 🟢 | `template_table` → `<user_table>` |
| 2 | Date column | 🟢 | `date` → `<user_date_col>` |
| ... | ... | ... | ... |

**New Cells:** <None or description>
**Removed Cells:** <None or description>

---
### Notebook 02: Exploratory Data Analysis

| # | Change | Risk | From → To |
|---|--------|------|-----------|
| 1 | Input table | 🟢 | `template_table` → `<user_table>` |
| 2 | Date column | 🟢 | `date` → `<user_date_col>` |
| ... | ... | ... | ... |

**New Cells:** <None or description>
**Removed Cells:** <None or description>

---
### Notebook 03: Profiling

| # | Change | Risk | From → To |
|---|--------|------|-----------|
| 1 | CV² threshold | 🟡 | 0.49 → <value> |
| ... | ... | ... | ... |

**New Cells:** <None or description>
**Removed Cells:** <None or description>

---

### Notebook 04: Clustering

| # | Change | Risk | From → To |
|---|--------|------|-----------|
| 1 | Skip clustering | 🟡 | Enabled → <Skip/Enabled> |
| ... | ... | ... | ... |

**New Cells:** <None or description>
**Removed Cells:** <None or description>

---

### Notebook 05: Feature Engineering

| # | Change | Risk | From → To |
|---|--------|------|-----------|
| 1 | Lag features | 🟡 | [1,7,14] → <new_lags> |
| 2 | External regressors | 🔴 | None → <regressor_cols> |
| ... | ... | ... | ... |

**New Cells:** <description of regressor integration if applicable>
**Removed Cells:** <None or description>

---

### Notebook 06: Train/Tune

| # | Change | Risk | From → To |
|---|--------|------|-----------|
| 1 | Forecast horizon | 🟢 | 4 → <horizon> |
| 2 | Model selection | 🔴 | LightGBM → <models> (if changed) |
| ... | ... | ... | ... |

**New Cells:** <None or description>
**Removed Cells:** <None or description>

---

### High-Risk Changes (Require Explicit Approval)

<If any high-risk changes, list them with detailed rationale>

| Change | Notebook | Rationale | Alternatives |
|--------|----------|-----------|--------------|
| <change> | <notebook> | <why needed> | <other options> |

---

**Please confirm:**
1. Does this plan look correct?
2. Any changes you'd like to add or remove?
3. For high-risk changes: Do you approve proceeding?
4. Ready to generate the customized notebooks?

Reply with your answers, then type `continue` to record this checkpoint. Start Phase 4 in a new chat using `tsf-04-notebook-generation.prompt.md` and the completion report path.
```

Checkpoint protocol (hard stop):
1. Log this checkpoint as **Pending** in `completion_report.md` (Checkpoint Log), including:
   - phase: `3`
   - notebook: (none)
   - cell index / step: `Checkpoint 3.1`
   - raw checkpoint text: the above checkpoint prompt
   - questions asked: the 4 confirmation items + any explicit high-risk approvals requested
   - answers: leave blank until user responds
2. Wait for the user to respond and type `continue`.
3. On `continue`, update the same checkpoint entry with the user’s answers and mark it completed, then STOP. The user will start Phase 4 in a new chat using `tsf-04-notebook-generation.prompt.md` and the completion report path.

## Handling Plan Modifications

If user requests changes to the plan:

```
📝 **Plan Updated**

I've incorporated your feedback:

**Changes Made:**
- <change 1>
- <change 2>

**Updated Plan:**
<show affected sections>

Does this updated plan look correct?
```

## Outputs for Next Phase

After user approves the plan, pass these to Phase 4:

- **scenario_name**: Confirmed folder name
- **output_folder**: Full path with timestamp
- **customization_plan**: Per-notebook detailed changes
  - notebook_01: list of {cell_id, change_type, old_value, new_value, risk}
  - notebook_01b: list of changes
  - notebook_02: list of changes
  - notebook_03: list of changes
  - notebook_04: list of changess
  - notebook_05: list of changes
- **new_cells**: Any cells to add (with code templates)
- **skip_sections**: Any sections/notebooks to skip
- **dependencies**: New packages to add to requirements.txt

## Phase Complete — STOP HERE

### Update Completion Report

Before stopping:
1. Read the existing completion report
2. Fill the **Phase 3: Customization Plan** section with:
   - Output folder path
   - Change summary by risk level
   - Per-notebook change tables
3. Mark Phase 3 as `[x]` complete in the Status section
4. Update the "Last Updated" timestamp
5. Save the updated completion report

### Present to User

```
✅ **Phase 3: Customization Plan Approved**

I've documented the customization plan in the completion report.

**STOPPING HERE.** To continue to Phase 4 (Notebook Generation & Validation):
1. Start a new conversation or continue in a new message
2. Reference the phase 4 prompt: `tsf-04-notebook-generation.prompt.md`
3. Provide the completion report path

Note: Phase 4 may take several minutes as each code cell is validated via Livy.
```
