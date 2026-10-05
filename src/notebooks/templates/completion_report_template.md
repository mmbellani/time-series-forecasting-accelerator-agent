# Time Series Forecasting Pipeline — Completion Report

**Scenario:** <!-- AGENT: Set in Phase 1 -->
**Created:** <!-- AGENT: Set in Phase 1 -->
**Last Updated:** <!-- AGENT: Update each phase -->

---

## Status

- [ ] Phase 1: Intake & Data Discovery
- [ ] Phase 2: Scenario Interpretation
- [ ] Phase 3: Customization Planning
- [ ] Phase 4: Notebook Generation & Validation
- [ ] Phase 5: Finalization & Delivery

---

## Checkpoint Log

<!--
AGENT INSTRUCTIONS
- Use this log to record every checkpoint stop as a first-class event.
- When a checkpoint is reached, create a new entry with Status = Pending.
- After the user responds and types `continue`, update the same entry:
  - Fill "User Answers"
  - Set Status = Completed

Required fields per entry:
- Phase (e.g., 1, 2, 3, 4.1, 4.2, 5)
- Notebook (if applicable)
- Cell/Step (cell index for notebooks, or "Checkpoint X.Y" for prompts)
- Raw Checkpoint Text
- Questions Asked
- User Answers
-->

### CP-0001 — <!-- AGENT: Increment ID -->

| Field | Value |
|------|-------|
| Status | ⏳ Pending |
| Phase | |
| Notebook | |
| Cell/Step | |

**Raw Checkpoint Text:**
> <!-- AGENT: Paste the checkpoint markdown/prompt text verbatim -->

**Questions Asked:**
1. <!-- AGENT -->
2. <!-- AGENT -->
3. <!-- AGENT -->

**User Answers:**
<!-- AGENT: Fill after user responds and types `continue` -->

---

## Phase 1: Data Discovery

<!-- AGENT: Fill this section when Phase 1 completes -->

### Checkpoints
<!-- AGENT: If Phase 1 paused at checkpoints, reference CP-#### entries from the Checkpoint Log -->

### Source and Execution Context

<!-- AGENT: Set data_source to exactly Fabric, Databricks, or Local. notebook_prefix
must equal data_source. Fill only applicable source fields, never credentials.
Preserve this context in every phase; do not infer Fabric from missing fields. -->

| Attribute | Value |
|-----------|-------|
| data_source | |
| notebook_prefix | |
| execution_environment | |
| source_details | |

### Fabric Connection (Fabric Only)
| Attribute | Value |
|-----------|-------|
| Workspace Name | |
| Workspace ID | |
| Lakehouse Name | |
| Lakehouse ID | |
| SQL Endpoint | |

### Databricks Connection (Databricks Only)
| Attribute | Value |
|-----------|-------|
| Workspace Host / Auth Profile Name | |
| Catalog / Schema | |
| Qualified Tables or File/Volume Paths | |
| SQL Warehouse / Compute | |
| File Formats / Read Options (if applicable) | |

### Local Files (Local Only)
| Attribute | Value |
|-----------|-------|
| Absolute File Paths | |
| Formats / Read Options | |
| Python/Jupyter Kernel | |
| Local Spark (if required) | |

### Source Data
| Attribute | Value |
|-----------|-------|
| Qualified Table(s) or Absolute File Path(s) | |
| Total Rows | |
| Date Range | |
| Unique Series | |

### Column Mapping
| Role | Column | Type |
|------|--------|------|
| Date | | |
| Target | | |
| Series ID | | |
| Additional IDs | | |

### Data Quality
| Column | Null % | Notes |
|--------|--------|-------|
| | | |

### Target Statistics
| Metric | Value |
|--------|-------|
| Min | |
| Max | |
| Mean | |
| Std Dev | |
| Zero Values | |

### User's Scenario Description
> <!-- AGENT: Paste user's original description -->

---

## Phase 2: Scenario Interpretation

<!-- AGENT: Fill this section when Phase 2 completes -->

### Checkpoints
<!-- AGENT: If Phase 2 paused at checkpoints, reference CP-#### entries from the Checkpoint Log -->

### Derived Scenario Name
<!-- AGENT: e.g., hardware_monthly_demand_forecast (folder: .output/hardware_monthly_demand_forecast_YYYYMMDD/) -->

### Inferred Parameters
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Time Granularity | | |
| Forecast Horizon | | |
| Series Structure | | |
| Seasonality | | |
| Intermittency Level | | |

### Column Assignments (Confirmed)
| Role | Column | Notes |
|------|--------|-------|
| Date | | |
| Target | | |
| Series ID | | |
| Static Features | | |
| External Regressors | | |

### Pipeline Configuration Preview
| Notebook | Key Settings |
|----------|--------------|
| 01 Data Prep | |
| 02 EDA | |
| 03 Profiling | |
| 04 Clustering | |
| 05 Features | |
| 06 Train/Tune | |

---

## Phase 3: Customization Plan

<!-- AGENT: Fill this section when Phase 3 completes -->

### Checkpoints
<!-- AGENT: If Phase 3 paused at checkpoints, reference CP-#### entries from the Checkpoint Log -->

### Output Folder
<!-- AGENT: e.g., .output/hardware_monthly_demand_forecast_20251130/ -->

### Notebook Files (`notebook_files`)

<!-- AGENT: Resolve notebook_prefix from Phase 1 to Fabric, Databricks, or Local.
Record full output paths and use these exact names for generation, checkpoints,
uploads, execution, and delivery. Shared templates remain unprefixed. -->

| Number | Generated Filename | Full Output Path |
|--------|--------------------|------------------|
| 01 | `<notebook_prefix> 01 DataPreparation.ipynb` | |
| 02 | `<notebook_prefix> 02 ExploratoryDataAnalysis.ipynb` | |
| 03 | `<notebook_prefix> 03 ProfilingIntermittent.ipynb` | |
| 04 | `<notebook_prefix> 04 Clustering.ipynb` | |
| 05 | `<notebook_prefix> 05 FeatureEngineering.ipynb` | |
| 06 | `<notebook_prefix> 06 TrainTestSelectTune.ipynb` | |

### Artifact Locations (`artifact_locations`)

<!-- AGENT: Record qualified tables or absolute file/model paths and formats.
Add a row per cluster-specific feature artifact. Update with actual locations in Phase 4.
Elsewhere in this report, "Output Table" also covers a recorded local file artifact. -->

| Logical Artifact | Table / File / Model Location | Format |
|------------------|-------------------------------|--------|
| prepared | | |
| profiled | | |
| clustered | | |
| features (global) | | |
| features_cluster_{group} | | |
| forecasts | | |
| models | | |

### Change Summary
| Risk Level | Count | Description |
|------------|-------|-------------|
| 🟢 Low | | |
| 🟡 Medium | | |
| 🔴 High | | |

### Notebook 01: Data Preparation
| Change | Risk | From → To |
|--------|------|-----------|
| | | |

### Notebook 02: Exploratory Data Analysis
| Change | Risk | From → To |
|--------|------|-----------|
| | | |

### Notebook 03: Profiling
| Change | Risk | From → To |
|--------|------|-----------|
| | | |

### Notebook 04: Clustering
| Change | Risk | From → To |
|--------|------|-----------|
| | | |

### Notebook 05: Feature Engineering
| Change | Risk | From → To |
|--------|------|-----------|
| | | |

### Notebook 06: Train/Tune
| Change | Risk | From → To |
|--------|------|-----------|
| | | |

---

## Phase 4: Notebook Generation & Execution

<!-- AGENT: Update this section incrementally as each sub-phase completes -->

### Checkpoints
<!-- AGENT: If Phase 4 paused at notebook checkpoints, reference CP-#### entries from the Checkpoint Log -->

### Summary
| Sub-Phase | Notebook | Status | Cells | Output Table | Completed |
|-----------|----------|--------|-------|--------------|-----------|
| 4.1 | `<notebook_prefix> 01 DataPreparation.ipynb` | ⏳ Not Started | - | - | - |
| 4.2 | `<notebook_prefix> 02 ExploratoryDataAnalysis.ipynb` | ⏳ Not Started | - | - | - |
| 4.3 | `<notebook_prefix> 03 ProfilingIntermittent.ipynb` | ⏳ Not Started | - | - | - |
| 4.4 | `<notebook_prefix> 04 Clustering.ipynb` | ⏳ Not Started | - | - | - |
| 4.5 | `<notebook_prefix> 05 FeatureEngineering.ipynb` | ⏳ Not Started | - | - | - |
| 4.6 | `<notebook_prefix> 06 TrainTestSelectTune.ipynb` | ⏳ Not Started | - | - | - |

---

### Phase 4.1: Notebook 01 - Data Preparation

<!-- AGENT: Fill when Phase 4.1 completes -->

| Attribute | Value |
|-----------|-------|
| Status | ⏳ Not Started |
| Started | |
| Completed | |
| Session ID | |
| Session Reused | |
| Cells Executed | |
| Errors Fixed | |
| Cells Skipped | |

**Output Table:** 
- Rows: 
- Columns: 
- Date Range: 

**Errors Encountered:**
<!-- AGENT: Document any errors and resolutions -->

---

### Phase 4.2: Notebook 02 - EDA

<!-- AGENT: Fill when Phase 4.2 completes -->

| Attribute | Value |
|-----------|-------|
| Status | ⏳ Not Started |
| Started | |
| Completed | |
| Session ID | |
| Session Reused | |
| Cells Executed | |
| Errors Fixed | |
| Cells Skipped | |

**Errors Encountered:**
<!-- AGENT: Document any errors and resolutions -->

---

### Phase 4.3: Notebook 03 - Profiling

<!-- AGENT: Fill when Phase 4.3 completes -->

| Attribute | Value |
|-----------|-------|
| Status | ⏳ Not Started |
| Started | |
| Completed | |
| Session ID | |
| Session Reused | |
| Cells Executed | |
| Errors Fixed | |
| Cells Skipped | |

**Output Table:** 
- Rows: 
- Columns: 

**Errors Encountered:**
<!-- AGENT: Document any errors and resolutions -->

---

### Phase 4.4: Notebook 04 - Clustering

<!-- AGENT: Fill when Phase 4.4 completes -->

| Attribute | Value |
|-----------|-------|
| Status | ⏳ Not Started |
| Started | |
| Completed | |
| Session ID | |
| Session Reused | |
| Cells Executed | |
| Errors Fixed | |
| Cells Skipped | |

**Output Table:** 
- Rows: 
- Columns: 

**Errors Encountered:**
<!-- AGENT: Document any errors and resolutions -->

---

### Phase 4.5: Notebook 05 - Feature Engineering

<!-- AGENT: Fill when Phase 4.5 completes -->

| Attribute | Value |
|-----------|-------|
| Status | ⏳ Not Started |
| Started | |
| Completed | |
| Session ID | |
| Session Reused | |
| Cells Executed | |
| Errors Fixed | |
| Cells Skipped | |

**Output Table:** 
- Rows: 
- Columns: 

**Errors Encountered:**
<!-- AGENT: Document any errors and resolutions -->

---

### Phase 4.6: Notebook 06 - Train/Tune

<!-- AGENT: Fill when Phase 4.6 completes -->

| Attribute | Value |
|-----------|-------|
| Status | ⏳ Not Started |
| Started | |
| Completed | |
| Session ID | |
| Session Reused | |
| Cells Executed | |
| Errors Fixed | |
| Cells Skipped | |

**Output Table:** 
- Rows: 
- Columns: 

**Errors Encountered:**
<!-- AGENT: Document any errors and resolutions -->

---

## Phase 5: Finalization & Delivery

<!-- AGENT: Fill this section when Phase 5 completes -->

### Checkpoints
<!-- AGENT: If Phase 5 paused at checkpoints, reference CP-#### entries from the Checkpoint Log -->

### Notebook Upload

<!-- AGENT: Fill after upload decision. Local execution needs no upload.
Lakehouse attachment applies only to Fabric; record Databricks workspace folder
and compute instead. Resolve notebook names from notebook_files. -->

| Attribute | Value |
|-----------|-------|
| Upload Status | ⏳ Not Started |
| Workspace | |
| Workspace Folder / Compute (Databricks) | |
| Notebooks Uploaded | |
| Overwrite Required | |
| Lakehouse Attached | |

| Notebook | Upload Status | Lakehouse |
|----------|---------------|-----------|
| `<notebook_prefix> 01 DataPreparation` | | |
| `<notebook_prefix> 02 ExploratoryDataAnalysis` | | |
| `<notebook_prefix> 03 ProfilingIntermittent` | | |
| `<notebook_prefix> 04 Clustering` | | |
| `<notebook_prefix> 05 FeatureEngineering` | | |
| `<notebook_prefix> 06 TrainTestSelectTune` | | |

---

### Table Archiving

<!-- AGENT: Fill if execution was performed -->

| Original Table | Archived As | Status |
|----------------|-------------|--------|
| df_final | archive_df_final | |
| df_profiling | archive_df_profiling | |
| df_profiling_cluster | archive_df_profiling_cluster | |
| df_features | archive_df_features | |
| <!-- scenario -->_forecasts | archive_<!-- scenario -->_forecasts | |

---

### Notebook Execution

<!-- AGENT: Fill if execution was performed -->

| Attribute | Value |
|-----------|-------|
| Execution Status | ⏳ Not Started |
| Started | |
| Completed | |
| Total Duration | |

| Notebook | Status | Job ID | Duration | Output Table |
|----------|--------|--------|----------|--------------|
| `<notebook_prefix> 01 DataPreparation` | ⏳ | | | |
| `<notebook_prefix> 02 ExploratoryDataAnalysis` | ⏳ | | | |
| `<notebook_prefix> 03 ProfilingIntermittent` | ⏳ | | | |
| `<notebook_prefix> 04 Clustering` | ⏳ | | | |
| `<notebook_prefix> 05 FeatureEngineering` | ⏳ | | | |
| `<notebook_prefix> 06 TrainTestSelectTune` | ⏳ | | | |

---

### Errors & Recovery

<!-- AGENT: Document any execution failures and fixes applied -->

---

### Deliverables

| File | Status |
|------|--------|
| `<notebook_prefix> 01 DataPreparation.ipynb` | |
| `<notebook_prefix> 02 ExploratoryDataAnalysis.ipynb` | |
| `<notebook_prefix> 03 ProfilingIntermittent.ipynb` | |
| `<notebook_prefix> 04 Clustering.ipynb` | |
| `<notebook_prefix> 05 FeatureEngineering.ipynb` | |
| `<notebook_prefix> 06 TrainTestSelectTune.ipynb` | |
| completion_report.md | |
| requirements.txt | |

---

### Warnings & Recommendations

<!-- AGENT: List any warnings or recommendations -->

---

### Next Steps

<!-- AGENT: Customize based on what was done -->

**If notebooks were uploaded and executed:**
- Forecasts are available at the recorded `artifact_locations` entry for forecasts.
- Review archived tables if needed: `archive_*`

**If notebooks were uploaded but not executed:**
1. Open the confirmed Fabric or Databricks workspace and configured runtime.
2. Run notebooks in order: 01 → 02 → 03 → 04 → 05 → 06.

**If notebooks are local only:**
1. Fabric execution: import to the confirmed workspace and attach the Lakehouse.
2. Databricks execution: import to the confirmed workspace folder and select compute.
3. Local execution: open in the configured Python/Jupyter kernel; no upload is needed.
4. Verify recorded data/model locations and run 01 → 02 → 03 → 04 → 05 → 06.

---

*Generated by Time Series Forecaster Agent*
