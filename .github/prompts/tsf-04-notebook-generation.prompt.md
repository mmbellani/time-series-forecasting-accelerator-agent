# Phase 4: Notebook Generation & Execution

Generate and execute a single customized notebook, creating real output tables in the Lakehouse.

## Prerequisites

- Phase 3 completed: Customization plan approved by user
- **Completion report** from Phase 3 (user provides path)
- **Notebook number** (01-06) — user specifies which notebook to build

### If Notebook Number Not Provided

Ask the user:

```
Which notebook would you like me to build and execute?

1. Notebook 01 - Data Preparation
2. Notebook 02 - Exploratory Data Analysis
3. Notebook 03 - Profiling
4. Notebook 04 - Clustering
5. Notebook 05 - Feature Engineering
6. Notebook 06 - Train/Tune

Please specify the notebook number (01-06).
```

## Phase Start — Read Completion Report

At the start of this phase:
1. Read the completion report from the path provided by user
2. Extract all prior phase data needed for notebook generation
3. **Validate dependencies** — ensure prior notebooks are complete

### Context from Prior Phases (via completion report):
  - scenario_name, output_folder path
  - customization_plan (per-notebook changes)
  - new_cells (cells to add with code templates)
  - skip_sections (sections/notebooks to skip)
  - dependencies (new packages if any)
  - workspace_id, lakehouse_id (for Livy sessions)
  - Phase 4.x status for prior notebooks

### Dependency Validation

Before starting, verify prior notebooks are complete:

| Notebook | Required Prior Status |
|----------|----------------------|
| 01 | None |
| 02 | Phase 4.1 (Notebook 01) must be ✅ Complete |
| 03 | Phase 4.2 (Notebook 02) must be ✅ Complete |
| 04 | Phase 4.3 (Notebook 03) must be ✅ Complete |
| 05 | Phase 4.4 (Notebook 04) must be ✅ Complete |
| 06 | Phase 4.5 (Notebook 05) must be ✅ Complete |

If dependency is missing, inform the user:

```
⚠️ Notebook <NN> depends on Notebook <NN-1>, which hasn't been completed yet.

Please run Phase 4.<N-1> first:
  Prompt: tsf-04-notebook-generation.prompt.md
  Notebook: <NN-1>
```

## Setup

### 1. Create Output Folder (If First Notebook)

If this is notebook 01, create the timestamped output folder:
```
.output/<scenario_name>_<YYYYMMDD>/
```

### 2. Initialize Livy Session

Follow the Livy Session Management Rules defined in the agent definition:

1. **Check for existing sessions** via `livy_list_sessions()`
2. **If idle session exists** → Reuse it
3. **If busy session exists** → Wait and poll every 10 minutes until idle
4. **If no session exists** → Create a new one
5. **Never close the session** — leave it alive for next sub-phase

## Cell-by-Cell Execution Process

For the specified notebook, build and execute incrementally:

1. **Read the template notebook** (e.g., `Fabric 01 DataPreparation.ipynb`)
2. **Read the customization plan** from completion report (Phase 3 section)
3. **For each cell** in the template:
   - Apply customizations (parameter substitution, structural changes)
   - If markdown cell: Append to output notebook (no execution)
   - If code cell: Execute via Livy, then append on success
4. **Save notebook incrementally** after each successful cell
5. **Update completion report** with sub-phase results

### Checkpoint Handling (Hard Stop)

During Phase 4 execution, treat notebook checkpoints as blocking stops.

**Detection:** any markdown cell whose text contains `✅ CHECK POINT`.

**When a checkpoint markdown cell is encountered:**
1. **Append the checkpoint markdown cell** to the output notebook.
2. **Save the output notebook** (so the pause point is visible in the artifact).
3. **Compute feasible diagnostics** relevant to the checkpoint before stopping (use the checkpoint text to decide what to compute). Examples:
   - “confirm configuration parameters / parameters” → show current parameter values and the inferred column mappings/table names.
   - “check missing values” → null counts by key columns; total nulls.
   - “list unique_id” → count unique ids; show a small sample (not the full list if huge).
   - “check the frequency” / “infer frequency” → inferred frequency + evidence (date diffs per series).
   - “count observations per id” → distribution of counts; top/bottom examples.
   - “duplicates” → count duplicate keys and sample offending rows/keys.
   - “set number of clusters to try” → series count + recommended search range; prior run results if available.
4. **Log a Pending checkpoint entry** in `completion_report.md` (Checkpoint Log) including:
   - phase: `4.<N>`
   - notebook: `0<N> <NotebookName>`
   - cell index / step: the template notebook cell index of this checkpoint markdown cell
   - raw checkpoint text: the checkpoint markdown content
   - questions asked: 1–3 concrete questions derived from the checkpoint text (prefer multiple-choice)
   - answers: leave blank until user responds
5. **Present the diagnostics + questions**, then **STOP immediately** and wait for the user to respond and type `continue`.

**Resume:**
- When the user provides answers and types `continue`, update the same checkpoint log entry with the user’s answers and mark it completed, then STOP.
- To resume execution, the user starts a new chat and re-runs this Phase 4 sub-phase prompt with the same completion report path; resume from the next template cell index (checkpoint cell index + 1). Do not re-run already-saved cells.

### Incremental Saving

The output notebook is saved **after each successful cell**:

```
After cell 1 succeeds → Save notebook with 1 cell
After cell 2 succeeds → Save notebook with 2 cells
After cell 3 succeeds → Save notebook with 3 cells
...
```

If the process fails at cell 8, the notebook on disk has cells 1-7 saved.

### No Output Capture

Save notebooks **without execution outputs** — clean cells only. User runs the notebook in Fabric to see fresh outputs.

---

## Notebook-Specific Customization Reference

### Notebook 01: Data Preparation

**Template:** `src/notebooks/Fabric 01 DataPreparation.ipynb`
**Output:** `<output_folder>/Fabric 01 DataPreparation.ipynb`

#### Customization Steps:

1. **Add header cell** (first cell):
   ```python
   """
   Time Series Forecasting Accelerator
   ====================================
   Scenario: <scenario_name>
   Generated: <YYYY-MM-DD>
   
   Key Parameters:
     - Date Column: <date_column>
     - Target Column: <target_column>
     - ID Columns: <id_columns>
     - Time Granularity: <granularity>
   
   This notebook was customized by the Time Series Forecaster agent.
   """
   ```

2. **Update table references**:
   - Input table: `<user_table>`
   - Output table: `<scenario_name>_prepared`

3. **Update column mappings**:
   - Date column: `<date_column>`
   - Target column: `<target_column>`
   - ID columns: `<id_columns>`

4. **Apply date parsing changes** (if needed)

5. **Add aggregation logic** (if granularity change needed):
   ```python
   # CUSTOMIZED: Aggregate daily data to weekly
   df = df.groupBy(
       F.date_trunc('week', F.col('<date_column>')).alias('<date_column>'),
       *[F.col(c) for c in <id_columns>]
   ).agg(
       F.sum('<target_column>').alias('<target_column>')
   )
   ```

---
### Notebook 02: Exploratory Data Analysis

**Template:** `src/notebooks/Fabric 02 ExploratoryDataAnalysis.ipynb`
**Output:** `<output_folder>/Fabric 02 ExploratoryDataAnalysis.ipynb`


# Phase 4.2: Exploratory Data Analysis

Generate and execute a customized EDA notebook on `df_final` (the output of Notebook 01 Data Preparation).

## Prerequisites

- Phase 4.1 completed: Notebook 01 has been executed and `<scenario>_prepared` table exists in the Lakehouse
- **Completion report** from prior phases (user provides path)
- Agent file `time-series-forecaster.md` provides persona and boundaries

## Phase Start — Read Completion Report

At the start of this phase:
1. Read the completion report from the path provided by user
2. Extract: `scenario_name`, `output_folder`, `workspace_id`, `lakehouse_id`
3. Extract from Phase 1: `date_var`, `unique_id`, `y` (target), `frequency`, `LAKEHOUSE_NAME`, prepared table name
4. Verify Phase 4.1 (Notebook 01) status is ✅ Complete

If Phase 4.1 is not complete:
```
⚠️ The EDA notebook depends on Notebook 01 (Data Preparation) being complete.

Please run Phase 4.1 first:
  Prompt: tsf-04-notebook-generation.prompt.md
  Notebook: 01
```

## Template Reference

Use `src/notebooks/Fabric 02 ExploratoryDataAnalysis.ipynb` as the template.
This template contains 9 sections that must be customized.

## Customization Steps

### Step 1: Read the Template

Read the template notebook from `src/notebooks/Fabric 02 ExploratoryDataAnalysis.ipynb`.

### Step 2: Apply Parameter Substitutions

Update the **Configuration** cell with values from the completion report:

| Parameter | Source |
|-----------|--------|
| `date_var` | Phase 1 data discovery (e.g., `'WEEK_START_DT'`) |
| `unique_id` | Phase 1 data discovery (e.g., `'STORE_LOCATION_ID'`) |
| `y` | Phase 1 data discovery (target column, e.g., `'TOTAL_NET_SALES'`) |
| `frequency` | Phase 1 data discovery (e.g., `'W'`) |
| `LAKEHOUSE_NAME` | Phase 1 Fabric connection |
| `INPUT_TABLE` | Phase 4.1 output table name (e.g., `'<scenario>_prepared'` or `'df_final'`) |

### Step 3: Customize Sections Based on Data Profile

Review the data profile from Phase 1 and customize each section:

#### Section 2 — Target Variable Distribution
- If target has **zeros or negatives**, keep `log1p` transform and zero/negative counts
- If target is always positive with no zeros, simplify to basic histogram + box plot
- If there are **very few series** (< 5), replace box-by-store with individual overlaid histograms

#### Section 3 — Time Series Trends
- Adjust Y-axis formatters based on target scale:
  - Millions → `f'{x/1e6:.1f}M'`
  - Thousands → `f'{x/1e3:.0f}K'`
  - Smaller → `f'{x:.0f}'`
- If **single series** (not panel data), remove the aggregate "all stores" plot and show only the single series

#### Section 4 — Seasonality Analysis
- Adapt to the actual frequency:
  - **Weekly data**: keep monthly + ISO-week seasonality
  - **Daily data**: add day-of-week seasonality, keep monthly
  - **Monthly data**: keep monthly only, replace weekly with quarterly
- If the date range spans **< 2 full cycles** of the primary seasonality, add a warning note

#### Section 5 — Store-Level Summary Statistics
- If `unique_id` is not "store" (e.g., it's "product", "SKU", "meter"), update all labels accordingly
- If **single series**, skip this section entirely (replace with a single-series statistics summary)

#### Section 6 — Correlation Analysis
- If there are **no numeric features** beyond the target, simplify or skip
- If there are **> 50 numeric features**, increase `top_n` to 30 and add a note about feature count
- If the data profile identified **potential external regressors** (promotions, holidays, weather), call them out explicitly in the correlation printout

#### Section 7 — Outlier Detection
- Keep IQR-based approach for all scenarios
- If **single series**, run outlier detection on the single series without the per-ID loop

#### Section 8 — Feature Distributions
- If **no categorical features** exist, remove the categorical section
- If there are **many numeric features** (> 20), increase `plot_cols` limit to 20 or add a second grid

#### Section 9 — Summary
- Update field labels to match actual column roles (e.g., "Products" instead of "Stores")
- Add scenario-specific observations from the data profile

### Step 4: Add Scenario-Specific Sections (If Applicable)

Based on the data profile from Phase 1, consider adding these optional sections:

| Condition | Additional Section |
|-----------|-------------------|
| Hierarchy detected (e.g., Store → Region) | **Hierarchy Analysis**: aggregate target by each hierarchy level, show level-by-level distributions |
| External regressors present (promotions, holidays) | **Regressor Impact**: compare target on promo vs non-promo periods, holiday vs non-holiday |
| High zero percentage (> 20%) | **Intermittency Preview**: show % zeros per series, preview of ADI/CV² that NB03 will compute |
| Multiple numeric regressors | **Feature Importance Preview**: quick random forest or mutual information ranking |

These additions are **medium risk** — ask the user before adding.

### Step 5: Save the Notebook

Save the customized notebook to:
```
.output/<scenario_name>_<YYYYMMDD>/Fabric 02 ExploratoryDataAnalysis.ipynb
```

## Execution

### Option A: Execute via Livy (Recommended)

Execute cells sequentially via Livy session, following the same protocol as Phase 4 notebook generation:

1. **Reuse or create a Livy session** (follow Livy Session Management Rules from agent definition)
2. Execute each code cell via `livy_run_statement()`
3. Capture outputs (especially the Section 9 summary)
4. On error: diagnose, fix, retry (up to 3 attempts per cell)

### Option B: Save Only (If User Prefers)

Save the notebook without executing. User can run it manually in Fabric.

## Checkpoint 2.1: Present EDA Findings

After execution, present findings:

```
📊 **EDA Summary — <scenario_name>**

**Dataset Overview:**
- Series: <n_stores> <series_type> (e.g., "50 stores")
- Time range: <date_range>, <n_periods> <freq>
- Total observations: <n_obs>

**Target Variable (<y>):**
- Range: <min> to <max>
- Mean: <mean>, Std: <std>
- Skewness: <skew>, Kurtosis: <kurt>
- Zeros: <n_zeros> (<pct>%), NAs: <n_na> (<pct>%)

**Key Observations:**
1. <trend observation>
2. <seasonality observation>
3. <outlier observation>
4. <correlation insight>

**Implications for Forecasting Pipeline:**
- <recommendation for NB03 profiling>
- <recommendation for NB04 clustering>
- <recommendation for NB05 features>
- <recommendation for NB06 modeling>

---

**Notebook saved to:** `.output/<scenario_name>_<YYYYMMDD>/Fabric 02 ExploratoryDataAnalysis.ipynb`

Reply with your observations, then type `continue` to record this checkpoint.
```

Checkpoint protocol (hard stop):
1. Log this checkpoint as **Pending** in `completion_report.md`:
   - phase: `4.2`
   - notebook: `Fabric 02 ExploratoryDataAnalysis.ipynb`
   - cell/step: `Checkpoint 2.1`
   - raw checkpoint text: the EDA summary above
   - questions asked: (none — informational checkpoint)
   - answers: leave blank until user responds
2. Wait for the user to respond and type `continue`.
3. On `continue`, update checkpoint entry with user's observations and mark completed, then STOP.

## Update Completion Report

Add a Phase 4.2 section to the completion report:

```markdown
### Phase 4.2: Exploratory Data Analysis

| Attribute | Value |
|-----------|-------|
| Status | ✅ Complete |
| Started | <date> |
| Completed | <date> |
| Session ID | <livy_session_id or "Not executed"> |

**Dataset Shape:** <rows> × <columns>
**Target Statistics:** mean=<>, std=<>, skew=<>, zeros=<>%
**Key Findings:**
1. <finding 1>
2. <finding 2>
3. <finding 3>

**Pipeline Recommendations:**
- <rec 1>
- <rec 2>
```

## Error Handling

- If Lakehouse table not found: fall back to local parquet at `data/<table_name>.parquet`
- If Livy session fails: save notebook without execution, inform user
- If a visualization cell fails (e.g., no categorical columns): catch gracefully with informative message, continue to next section



---
### Notebook 03: Profiling & Intermittent Classification

**Template:** `src/notebooks/Fabric 03 ProfilingIntermittent.ipynb`
**Output:** `<output_folder>/Fabric 03 ProfilingIntermittent.ipynb`

#### Customization Steps:

1. **Add header cell** with scenario metadata

2. **Update table references**:
   - Input table: `<scenario_name>_prepared`
   - Output table: `<scenario_name>_profiled`

3. **Update threshold parameters**:
   ```python
   # CUSTOMIZED: Adjusted thresholds based on data profile
   CV2_THRESHOLD = <cv2_value>  # Default: 0.49
   ADI_THRESHOLD = <adi_value>  # Default: 1.32
   ```

4. **If skipping profiling** (single series):
   ```python
   # CUSTOMIZED: Profiling skipped for single series
   df_profiled = spark.table('<scenario_name>_prepared')
   df_profiled = df_profiled.withColumn('demand_class', F.lit('Regular'))
   df_profiled.write.mode('overwrite').saveAsTable('<scenario_name>_profiled')
   ```

## Error Handling

- If Lakehouse table not found: fall back to local parquet at `data/<table_name>.parquet`
- If Livy session fails: save notebook without execution, inform user
- If a visualization cell fails (e.g., no categorical columns): catch gracefully with informative message, continue to next section
---

### Notebook 04: Clustering

**Template:** `src/notebooks/Fabric 04 Clustering.ipynb`
**Output:** `<output_folder>/Fabric 04 Clustering.ipynb`

#### Customization Steps:

1. **Add header cell** with scenario metadata

2. **Confirm clustering approach** (based on Phase 3 customization plan):
   - Use the main template and adjust parameters/skip logic as needed

3. **Update table references**:
   - Input table: `<scenario_name>_profiled`
   - Output table: `<scenario_name>_clustered`

4. **If skipping clustering**:
   ```python
   # CUSTOMIZED: Clustering skipped — <reason>
   df_clustered = spark.table('<scenario_name>_profiled')
   df_clustered = df_clustered.withColumn('cluster_id', F.lit(0))
   df_clustered.write.mode('overwrite').saveAsTable('<scenario_name>_clustered')
   ```

5. **If enabling clustering**, update parameters:
   ```python
   # CUSTOMIZED: Cluster count based on series count
   N_CLUSTERS = <n_clusters>
   ```
## Error Handling

- If Lakehouse table not found: fall back to local parquet at `data/<table_name>.parquet`
- If Livy session fails: save notebook without execution, inform user
- If a visualization cell fails (e.g., no categorical columns): catch gracefully with informative message, continue to next section
---

### Notebook 05: Feature Engineering

**Template:** `src/notebooks/Fabric 05 FeatureEngineering.ipynb`
**Output:** `<output_folder>/Fabric 05 FeatureEngineering.ipynb`

#### Key Sections in Template

The template has two major phases:

**Phase A — Data Type Classification** (under "Ensure Proper Data Types"):
Columns are classified into five categories before feature engineering begins:

| Type | Detection Logic | Treatment |
|------|----------------|-----------|
| **Date** | Extracted from `ds`: year, month, week | Used as calendar features |
| **Static** | Columns constant within each `unique_id` (`get_static_cols()`) | Cast to `category` dtype |
| **Numeric** | `float64`, `float32`, `int64` columns (excluding binary/static) | Used as-is for lags/rolling |
| **Binary** | Columns with only values {0, 1} (`get_binary_cols()`) | Cast to `category` |
| **Categorical** | Object/category/bool columns (not static, not date-derived) | Cast to `category` |

**Phase B — Feature Engineering** (MLForecast-based, runs at two levels):

| Level | What happens |
|-------|-------------|
| **Global** | `fcst.preprocess()` on the full dataset → global correlation analysis → global XGBoost feature importance |
| **Per profile_cluster** | Loop over `df['profile_cluster'].unique()` → per-cluster `fcst_by_cluster.preprocess()` → per-cluster correlations + XGBoost importance → side-by-side comparison heatmap |

#### Customization Steps:

1. **Add header cell** with scenario metadata

2. **Update table references**:
   - Input table: `<scenario_name>_clustered`
   - Output table: `<scenario_name>_features`

3. **Update data type classification** (if needed based on data profile):
   ```python
   # CUSTOMIZED: Override column type assignments if auto-detection is incorrect
   # Force specific columns into categories:
   STATIC_OVERRIDES = <list>      # e.g., ['REGION', 'STORE_TYPE']
   NUMERIC_OVERRIDES = <list>     # e.g., ['TEMPERATURE', 'PRICE']
   CATEGORICAL_OVERRIDES = <list> # e.g., ['PROMO_TYPE']
   BINARY_OVERRIDES = <list>      # e.g., ['IS_HOLIDAY', 'IS_WEEKEND']
   ```

4. **Update lag configuration**:
   ```python
   # CUSTOMIZED: Lag features based on <seasonality> seasonality
   LAG_PERIODS = <lag_list>  # e.g., [1, 7, 14, 21, 28]
   ```

5. **Update rolling window configuration**:
   ```python
   # CUSTOMIZED: Rolling windows for trend detection
   ROLLING_WINDOWS = <window_list>  # e.g., [7, 14, 28]
   ```

6. **Configure calendar features**:
   ```python
   # CUSTOMIZED: Calendar features for <granularity> data
   INCLUDE_DAY_OF_WEEK = <True/False>
   INCLUDE_MONTH = <True/False>
   INCLUDE_QUARTER = <True/False>
   INCLUDE_YEAR = <True/False>
   ```

7. **Configure per-cluster feature engineering**:
   - The template runs feature engineering both globally and per `profile_cluster`
   - If **single cluster** (e.g., all series classified the same): skip the per-cluster loop
   - If **many clusters** (> 5): consider limiting the per-cluster XGBoost plots to top-N clusters by series count

8. **Add external regressors** (if applicable):
   ```python
   # CUSTOMIZED: External regressor integration
   REGRESSOR_COLUMNS = <regressor_list>
   
   # Join regressor data
   df_regressors = spark.table('<regressor_table>')
   df = df.join(df_regressors, on=[<join_keys>], how='left')
   ```
## Error Handling

- If Lakehouse table not found: fall back to local parquet at `data/<table_name>.parquet`
- If Livy session fails: save notebook without execution, inform user
- If a visualization cell fails (e.g., no categorical columns): catch gracefully with informative message, continue to next section
---

### Notebook 06: Train/Test/Select/Tune

**Template:** `src/notebooks/Fabric 06 TrainTestSelectTune.ipynb`
**Output:** `<output_folder>/Fabric 06 TrainTestSelectTune.ipynb`

#### Checkpoints in This Notebook

The template contains **3 checkpoints** that require user input:

| # | Checkpoint Text | User Decision Required |
|---|----------------|------------------------|
| 6.1 | `✅ CHECK POINT with the data scientist: set prediction start date and prediction end date` | User must specify `training_start_date` and `training_end_date` for the rolling evaluation window. Present an aggregated plot of the target variable (sum across all series and by profile_cluster) to help the user choose. |
| 6.2 | `✅ CHECK POINT with the data scientist: set out-of-sample period` | User must specify `oos_start_date` and `oos_end_date`. The OOS period **must** be after the training period (to avoid data leakage). Present the chart with training window highlighted and ask for OOS boundaries. |
| 6.3 | `✅ CHECK POINT with the data scientist: ask if you want to use additional regressors` | Based on findings from the EDA notebook (02), ask if the user wants to include additional exogenous regressors (e.g., promotions, holidays, temperature) in the model. Present the correlation/feature importance findings from EDA. |

Each checkpoint follows the standard **Checkpoint Stop Protocol**: compute diagnostics, present summary + questions, log as Pending in `completion_report.md`, then STOP.

#### Customization Steps:

1. **Add header cell** with scenario metadata

2. **Update table references**:
   - Global input table: `<scenario_name>_features` (full feature dataset from NB05)
   - Per-cluster input tables: `<scenario_name>_features_cluster_{group}` (per-cluster feature datasets from NB05)
   - Output table: `<scenario_name>_forecasts`
   - Profile-cluster table: `<scenario_name>_clustered` (for loading profile_cluster mappings)

3. **Update configuration parameters**:
   ```python
   # CUSTOMIZED: Time series configuration
   date_var = '<date_column>'
   unique_id = '<id_column>'
   y = '<target_column>'
   frequency = '<freq>'  # e.g., 'W', 'MS', 'D'
   selection_metric = '<metric>'  # e.g., 'MAE', 'WMAPE', 'RMSE'
   INPUT_TABLE_NAME = "<lakehouse>.<scenario_name>_features"
   PROFILE_CLUSTER_TABLE_NAME = "<lakehouse>.<scenario_name>_clustered"
   ```

4. **Configure train/test split** (set after Checkpoint 6.1):
   ```python
   # CUSTOMIZED: Training evaluation window (set by user at checkpoint)
   training_start_date = pd.to_datetime("<user_specified>")
   training_end_date = pd.to_datetime("<user_specified>")
   ```

5. **Configure out-of-sample period** (set after Checkpoint 6.2):
   ```python
   # CUSTOMIZED: Out-of-sample period (set by user at checkpoint)
   oos_start_date = pd.to_datetime("<user_specified>")
   oos_end_date = pd.to_datetime("<user_specified>")
   ```

6. **Update model configuration** (if changed):
   ```python
   # CUSTOMIZED: Target transform configurations
   transform_configs = {
       "identity": [],
       "std": [LocalStandardScaler()],
       "diff1": [Differences([1])],
   }
   ```

7. **Update hyperparameter ranges**:
   ```python
   # CUSTOMIZED: Hyperparameter search space
   PARAM_SPACE = {
       'num_leaves': (20, 100),
       'learning_rate': (0.01, 0.3),
       'n_estimators': (50, 500),
       # ... additional parameters
   }
   ```

8. **Configure evaluation metrics**:
   ```python
   # CUSTOMIZED: Selection metric for best model
   selection_metric = '<metric>'  # e.g., 'MAE', 'WMAPE', 'RMSE'
   ```

9. **Configure lag features**:
   ```python
   # CUSTOMIZED: Lag features based on seasonality
   lags = <lag_list>  # e.g., [1, 2] for monthly, [1, 7, 14] for daily
   ```

10. **Add profile_cluster column** (derived from Notebooks 04 and 05):
    ```python
    # CUSTOMIZED: Create profile_cluster variable
    # Rule: profile_cluster = profile; where profile == 'regular', substitute with cluster value
    # Then remove 'profile' and 'cluster' columns from the DataFrame
    df['profile_cluster'] = df['profile']
    df.loc[df['profile'] == 'regular', 'profile_cluster'] = df['cluster'].astype(str)
    df.drop(columns=['profile', 'cluster'], inplace=True, errors='ignore')
    ```

11. **Configure additional regressors** (set after Checkpoint 6.3, based on EDA findings):
    ```python
    # CUSTOMIZED: Additional exogenous regressors (user-approved at checkpoint)
    REGRESSOR_COLUMNS = <regressor_list>  # e.g., ['temperature', 'is_promo', 'holiday_flag']
    ```

#### Training Strategy: Global + By Profile-Cluster

The notebook trains models in **two passes** using different feature datasets produced by Notebook 05, then compares results:

**Pass 1 — Global Model:**
- **Input data:** `<scenario_name>_features` (the full global feature table from Notebook 05 containing ALL series)
- Train LightGBM with multiple target transforms (identity, StandardScaler, Differences) on **all training data**
- Use rolling-origin evaluation across the training window
- Generate out-of-sample forecasts for the OOS period
- Compute WMAPE, MAE, RMSE for each transform variant
- Select the best-performing transform

**Pass 2 — By Profile-Cluster:**
- For each `profile_cluster` group, load the **dedicated per-cluster feature table** created by Notebook 05:
  - Lakehouse table: `<scenario_name>_features_cluster_{group}` (e.g., `_features_cluster_0`, `_features_cluster_intermittent`)
  - Local fallback: `data/df_features_cluster_{group}.parquet`
- Train a separate LightGBM model using only the series and features from that cluster's table
- Apply the same rolling-origin evaluation and OOS forecasting
- Compute per-group and overall metrics
- Compare global vs. per-group performance

**Key data flow from Notebook 05:**
| Training Pass | Feature Data Source | Series Scope |
|---------------|--------------------|--------------| 
| Global | `<scenario_name>_features` | All series together |
| Per profile_cluster | `<scenario_name>_features_cluster_{group}` | Only series in that group (may have cluster-specific features) |

**Comparison Visualization:**
- Generate a chart showing:
  - Historical actual data (black line)
  - Forecast from the global model (one color)
  - Forecast from the profile-cluster models (different color)
  - Two vertical lines marking `training_start_date` and `training_end_date`
  - Shaded area between them to visually identify the training evaluation set
  - OOS period clearly marked

**Final Output:**
- Save the best forecasts (global or by-group, whichever performs better per metric) to the output table `<scenario_name>_forecasts`
- Log all model runs and metrics to MLflow
---

## Retry Protocol

### For Each Code Cell:

1. **Execute via Livy**:
   ```
   result = livy_run_statement(workspace_id, lakehouse_id, session_id, cell_code, with_wait=True)
   ```

2. **Check result state**:
   - `available` with `status: ok` → Success, append cell to notebook
   - `available` with `status: error` → Error, apply retry protocol
   - `error` state → Session error, check logs

### Retry Attempts

| Attempt | Action |
|---------|--------|
| 1 | Execute original customized code |
| 2 | Analyze error, apply fix (syntax, imports, column names, types) |
| 3 | Try alternative approach if applicable |

### User Escalation (After 3 Failed Attempts)

If all retries fail, ask the user inline:

```
⚠️ **Cell Execution Failed — Your Input Needed**

**Notebook:** Fabric 0<N> <NotebookName>.ipynb
**Cell:** <cell number> of <total cells> (<cell description>)

**Code:**
```python
<problematic code>
```

**Error:**
```
<error message>
```

**Attempted Fixes:**
1. <fix 1> → <outcome>
2. <fix 2> → <outcome>

**Options:**
A) <suggested fix approach>
B) Skip this cell and continue (may affect downstream logic)
C) Abort this sub-phase (you can fix and re-run)
D) Provide your own fix

How would you like to proceed?
```

### User Response Handling

| User Choice | Agent Action |
|-------------|--------------|
| A (suggested fix) | Apply fix, re-execute, continue if successful |
| B (skip) | Add cell with `# SKIPPED` marker, log reason, continue |
| C (abort) | Stop sub-phase, update completion report with partial status, exit |
| D (custom fix) | User provides code, agent executes it, continues if successful |

### Skipped Cells

If user chooses to skip a cell, add it with a marker:

```python
# ⚠️ SKIPPED — Execution failed after 3 attempts
# Error: <error message>
# See completion report Phase 4.<N> for details
# <original code commented out>
```

---

### Session Recovery
- If session dies mid-execution, create a new session
- Resume from the last successfully saved cell
- Log session recovery in completion report

### Resource Errors
- If Spark memory errors occur, suggest reducing data sample
- Note in completion report that full data execution wasn't possible

## Error Handling
- If Lakehouse table not found: fall back to local parquet at `data/<table_name>.parquet`
- If Livy session fails: save notebook without execution, inform user
- If a visualization cell fails (e.g., no categorical columns): catch gracefully with informative message, continue to next section


---

## Sub-Phase Completion

### Update Completion Report

Before stopping:
1. Read the existing completion report
2. Update the **Phase 4 Summary table** row for this notebook
3. Fill the **Phase 4.N** detail section with:
   - Status, timestamps
   - Session info (ID, reused or new)
   - Cells executed, errors fixed, cells skipped
   - Output table stats
   - Errors encountered
4. Update the "Last Updated" timestamp
5. Save the updated completion report

### Present to User

For notebooks 01-04:

```
✅ **Phase 4.<N> Complete — Notebook 0<N> <NotebookName>**

| Metric | Value |
|--------|-------|
| Cells Executed | <X> |
| Errors Auto-Fixed | <N> |
| Cells Skipped | <N> |
| Output Table | <scenario_name>_<suffix> (<Y> rows) |

**Notebook saved to:**
`<output_folder>/Fabric 0<N> <NotebookName>.ipynb`

---

**Next Step:** Run Phase 4.<N+1> to build Notebook 0<N+1>

  Prompt: tsf-04-notebook-generation.prompt.md
  Completion report: <completion_report_path>
  Notebook: 0<N+1>
```

### After Phase 4.6 (Final Notebook) Completes

```
✅ **Phase 4.6 Complete — Notebook 06 Train/Tune**

All 6 notebooks have been built and executed successfully!

| Notebook | Status | Output Table |
|----------|--------|--------------|
| 01 Data Preparation | ✅ | <scenario>_prepared |
| 02 Exploratory Data Analysis | ✅ | — (analysis only) |
| 03 Profiling | ✅ | <scenario>_profiled |
| 04 Clustering | ✅ | <scenario>_clustered |
| 05 Feature Engineering | ✅ | <scenario>_features |
| 06 Train/Tune | ✅ | <scenario>_forecasts |

---

**Next Step:** Run Phase 5 to finalize the completion report

  Prompt: tsf-05-finalization.prompt.md
  Completion report: <completion_report_path>
```

---

## STOP HERE — Do Not Auto-Proceed

After completing the specified notebook:
1. Update the completion report
2. Present the summary to the user
3. **STOP** — do not automatically proceed to the next notebook

The user will start the next sub-phase in a new conversation turn.
