# Phase 1: Intake & Data Discovery

Read the user's data from Microsoft Fabric, Databricks, or local files and analyze it
to understand the forecasting scenario.

## Prerequisites

- User has access to the selected source: a Fabric Lakehouse, Databricks table/file,
  or local file(s)
- Agent file `time-series-forecaster.md` provides persona and boundaries

## Phase 0: Gather Required Inputs

If required inputs are missing, ask one question at a time. First confirm the data
source, then ask only for the connection or file details relevant to that source.
Use the following intake checklist; do not request credentials or secrets in chat.

```
🔮 **Time Series Forecasting Accelerator**

I'll help you customize the forecasting pipeline for your specific dataset and scenario.

To get started, I need:

1. **Data Source**: Microsoft Fabric, Databricks, or Local?
2. **Source Details**:
   - Fabric: workspace, Lakehouse, and table name(s).
   - Databricks: workspace host/profile, catalog, schema, and table name(s), or
     accessible file/Volume paths and formats; SQL warehouse or compute for access.
   - Local: absolute file path(s), format (e.g., CSV, Parquet, Excel), and any
     required read options (sheet, delimiter, encoding).
3. **Execution Environment**: Where should the notebooks run? Normally this matches
   the source; for local data, identify the Python/Jupyter kernel and whether Spark
   is available. Confirm output data/model locations and remote compute when needed.
4. **Scenario Description**: Describe your forecasting use case in a few sentences.
   - What are you forecasting? (e.g., sales, demand, inventory)
   - What's your forecast horizon? (e.g., next 4 weeks, 12 months ahead)
   - Any specific requirements? (e.g., weekly aggregation, by region, include promotions)

**Example scenario:**
> "We need to forecast weekly product demand for 500 SKUs across 10 stores 
> for the next 8 weeks. We have 3 years of history. Some products are 
> intermittent sellers. We want to use promotional calendar data as an 
> external regressor."
```

Wait for the user to provide all required inputs before proceeding.

### Source and Notebook Naming Contract

Persist these fields in `completion_report.md` for every later phase:

- `data_source`: exactly `Fabric`, `Databricks`, or `Local`.
- `notebook_prefix`: identical to `data_source`; based on where the input data is
  read, not the template name or where the generated notebook file is stored.
- `source_details`: verified source-specific connection identifiers or absolute
  file paths, formats, and read options (no secrets).
- `execution_environment`: confirmed runtime/compute and non-secret connection profile.
- `artifact_locations`: explicit locations/formats for prepared, profiled, clustered,
  global/per-cluster feature, forecast, and model outputs, filled as planning proceeds.

All generated notebooks must use `<notebook_prefix> <NN> <NotebookName>.ipynb`:

| Number | Generated filename |
|--------|--------------------|
| 01 | `<notebook_prefix> 01 DataPreparation.ipynb` |
| 02 | `<notebook_prefix> 02 ExploratoryDataAnalysis.ipynb` |
| 03 | `<notebook_prefix> 03 ProfilingIntermittent.ipynb` |
| 04 | `<notebook_prefix> 04 Clustering.ipynb` |
| 05 | `<notebook_prefix> 05 FeatureEngineering.ipynb` |
| 06 | `<notebook_prefix> 06 TrainTestSelectTune.ipynb` |

For example: `Fabric 01 DataPreparation.ipynb`, `Databricks 01 DataPreparation.ipynb`,
or `Local 01 DataPreparation.ipynb`. Resolve the placeholder before saving files,
logging checkpoints, or displaying notebook names. Keep the unprefixed templates in
`src/notebooks/` unchanged. If multiple source types are involved, ask which is the
primary forecasting input and use its prefix consistently; record all auxiliary sources.
Never change the source or prefix silently on connection failure.

## Phase 1.1: Connect to the Selected Source

Discover the available tools or configured connectors before calling them. Reuse
existing authenticated access and verify read permissions. Follow only the matching
branch below; Fabric workspace/Lakehouse IDs are not required for other sources.

### Fabric

1. **List workspaces** to verify access:
   ```
   list_workspaces()
   ```
   - Confirm the user's workspace exists and is accessible
   - If not found, ask user to verify the workspace name

2. **Get workspace details**:
   ```
   list_items(workspace_name=<user_workspace>, item_type="Lakehouse")
   ```
   - Confirm the Lakehouse exists
   - Note the Lakehouse ID for later Livy session creation

3. **Get SQL endpoint** for data querying:
   ```
   get_sql_endpoint(workspace_name=<user_workspace>, item_name=<lakehouse_name>, item_type="Lakehouse")
   ```

### Databricks

1. Verify the user-selected workspace and configured authentication profile.
2. Use the available Databricks connector, SQL warehouse, or compute to verify the
   catalog/schema/table or file path. Do not assume a default workspace or catalog.
3. Record fully qualified table identifiers (`catalog.schema.table`) or file paths,
   formats, read options, and the warehouse/compute identifier.
4. Inspect schemas and small samples with Databricks SQL/Spark. If access or execution
   tooling is unavailable, report the blocker and request configuration; do not
   substitute Fabric tools or claim a successful connection.

### Local

1. Resolve and verify the provided file paths without modifying the source files.
2. Read schema and a small sample using the format-appropriate reader in the confirmed
   local environment; apply the specified sheet/delimiter/encoding options.
3. Record absolute paths and read options. For multiple files, confirm whether they
   should be concatenated or joined and verify schema/key compatibility.
4. Confirm local output locations. No workspace, Lakehouse, or cloud upload is required.

## Phase 1.2: Analyze Data Schema

Inspect the data using the selected source. The SQL below illustrates Fabric SQL
endpoint queries, not a mandatory access path:

- Fabric: use schema-qualified tables and SQL endpoint syntax.
- Databricks: use qualified catalog/schema/table identifiers, `DESCRIBE TABLE` or
  catalog metadata, `SELECT ... LIMIT 5`, and Spark/Databricks SQL aggregates.
- Local: use the loaded DataFrame's schema/dtypes, row count, date min/max, and
  `head(5)` (or equivalent). Apply the same profiling checks without issuing cloud SQL.

1. **Get table schema**:
   ```sql
   SELECT column_name, data_type 
   FROM INFORMATION_SCHEMA.COLUMNS 
   WHERE table_name = '<table_name>'
   ORDER BY ordinal_position
   ```

2. **Get row count and date range**:
   ```sql
   SELECT 
     COUNT(*) as total_rows,
     MIN(<date_column>) as min_date,
     MAX(<date_column>) as max_date
   FROM <table_name>
   ```
   - If date column is unknown, query a sample first to identify it

3. **Get sample data** (first 5 rows):
   ```sql
   SELECT TOP 5 * FROM <table_name>
   ```

## Phase 1.3: Profile the Data

Gather statistics needed for customization decisions:

Adapt the examples to the source's SQL dialect or local DataFrame API. For multiple
ID columns, count distinct ID tuples rather than concatenating them. Use `STDDEV_SAMP`
in Databricks or the equivalent sample standard deviation locally instead of Fabric's
`STDEV`. Report whether statistics cover the full dataset or only a sample.

1. **Identify key columns** by analyzing schema and sample:
   - Date/timestamp column (for time series ordering)
   - Target column (what we're forecasting)
   - ID columns (product, store, region, etc. for multi-series)
   - Potential external regressors (promotions, holidays, weather)

2. **Count unique series**:
   ```sql
   SELECT COUNT(DISTINCT <id_columns>) as series_count
   FROM <table_name>
   ```

3. **Analyze time granularity**:
   ```sql
   SELECT 
     <date_column>,
     LEAD(<date_column>) OVER (PARTITION BY <id_columns> ORDER BY <date_column>) as next_date
   FROM <table_name>
   ```
   - Calculate typical gaps to infer granularity (daily, weekly, monthly)

4. **Check data quality**:
   ```sql
   SELECT 
     '<column_name>' as column_name,
     COUNT(*) as total_rows,
     SUM(CASE WHEN <column_name> IS NULL THEN 1 ELSE 0 END) as null_count,
     CAST(SUM(CASE WHEN <column_name> IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS DECIMAL(5,2)) as null_pct
   FROM <table_name>
   ```
   - Run for each important column

5. **Target variable statistics**:
   ```sql
   SELECT 
     MIN(<target_column>) as min_value,
     MAX(<target_column>) as max_value,
     AVG(<target_column>) as avg_value,
     STDEV(<target_column>) as std_value,
     SUM(CASE WHEN <target_column> = 0 THEN 1 ELSE 0 END) as zero_count
   FROM <table_name>
   ```

6. **Check for hierarchy** (if multiple ID columns):
   - Analyze grouping columns to understand hierarchy structure
   - Example: Product → Category → Department, or Store → Region → Country

## Checkpoint 1.1: Present Data Profile

Present findings to the user for confirmation:

```
📊 **Data Profile Summary**

**Data Source:** <data_source>
**Source Location:** <verified table identifier or absolute file path(s)>
**Execution Environment:** <execution_environment>
**Notebook Prefix:** <notebook_prefix>

**Volume:**
- Total rows: <row_count>
- Date range: <min_date> to <max_date> (<N> months)
- Unique series: <series_count>

**Detected Columns:**
| Column | Type | Role (Inferred) |
|--------|------|-----------------|
| <col1> | <type> | Date column |
| <col2> | <type> | Target (forecast this) |
| <col3> | <type> | Series ID |
| ... | ... | ... |

**Time Granularity:** <Daily/Weekly/Monthly> (based on date gaps)

**Data Quality:**
| Column | Null % | Notes |
|--------|--------|-------|
| <col1> | <pct>% | <any issues> |
| ... | ... | ... |

**Target Variable:**
- Range: <min> to <max>
- Mean: <avg>, Std Dev: <std>
- Zero values: <count> (<pct>%) — <comment on intermittency if high>

**Hierarchy Structure:** 
<Describe inferred hierarchy or "Single level (no hierarchy detected)">

---

**Please confirm:**
1. Is my column role detection correct?
2. Is the inferred time granularity correct?
3. Any columns I should treat differently?

Reply with your answers, then type `continue` to record this checkpoint. Start Phase 2 in a new chat using `tsf-02-scenario-interpretation.prompt.md` and the completion report path.
```

Checkpoint protocol (hard stop):
1. Log this checkpoint as **Pending** in `completion_report.md` (Checkpoint Log), including:
   - phase: `1`
   - notebook: (none)
   - cell index / step: `Checkpoint 1.1`
   - raw checkpoint text: the above checkpoint prompt
   - questions asked: the 3 confirmation questions
   - answers: leave blank until user responds
2. Wait for the user to answer and type `continue`.
3. On `continue`, update the same checkpoint entry with the user’s answers and mark it completed, then STOP. The user will start Phase 2 in a new chat using `tsf-02-scenario-interpretation.prompt.md` and the completion report path.

## Error Handling

### Fabric Workspace/Lakehouse Not Found
```
❌ **Connection Error**

I couldn't find workspace "<workspace_name>" or lakehouse "<lakehouse_name>".

Available workspaces:
<list workspaces>

Please verify the names and try again.
```

### Table Not Found
```
❌ **Table Not Found**

Table "<table_name>" was not found in <selected source namespace>.

Available tables:
<list accessible tables in the selected Lakehouse or catalog/schema>

Please provide the correct table name.
```

### Databricks Connection or Local File Errors
- Report the inaccessible workspace, compute, table, or file and the specific error.
- Ask for corrected identifiers, access configuration, file paths, or read options.
- Do not fall back to another source or invent data to continue.

### Query or Reader Errors
- Analyze the error message
- Adjust syntax for Fabric SQL, Databricks SQL/Spark, or the local file reader
- Retry with the corrected query/read options; surface any remaining blocker

## Outputs for Next Phase

After user confirms the data profile, pass these to Phase 2:

- **data_source**, **notebook_prefix**: Confirmed values from the naming contract
- **source_details**: Fabric workspace/Lakehouse IDs and qualified tables; Databricks
  host/profile, catalog/schema/tables or file paths and warehouse/compute; or local
  absolute file paths, formats, and read options. Store only the applicable fields.
- **execution_environment**: Confirmed runtime/compute
- **artifact_locations**: Confirmed output storage, refined in Phase 3
- **column_mapping**: Confirmed column roles
  - date_column
  - target_column
  - id_columns (list)
  - external_regressor_columns (list, if any)
- **data_profile**: Statistics gathered
  - row_count
  - date_range (min, max)
  - series_count
  - time_granularity
  - null_rates
  - target_stats
  - hierarchy_structure

## Completion Report File Location

Create the working output folder and completion report at:

` .output/<scenario_name>_<YYYYMMDD>/completion_report.md `

This output folder is intended to be ephemeral/local and should be gitignored.
- **scenario_description**: User's original description

## Phase Complete — STOP HERE

### Update Completion Report

Before stopping, create the completion report:
1. Copy template from `src/notebooks/templates/completion_report_template.md`
2. Save to `.output/<scenario_name>_<YYYYMMDD>/completion_report.md`
3. Fill the **Phase 1: Data Discovery** section with all gathered data, including the
   source/naming contract and applicable connection or file details
4. Mark Phase 1 as `[x]` complete in the Status section
5. Set the scenario name and timestamps

### Present to User

```
✅ **Phase 1: Data Discovery Complete**

I understand your data structure. I've saved the data profile to:
`.output/<scenario_name>_<YYYYMMDD>/completion_report.md`

**STOPPING HERE.** To continue to Phase 2 (Scenario Interpretation):
1. Start a new conversation or continue in a new message
2. Reference the phase 2 prompt: `tsf-02-scenario-interpretation.prompt.md`
3. Provide the completion report path
