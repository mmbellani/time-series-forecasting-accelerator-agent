# Phase 1: Intake & Data Discovery

Connect to the user's Fabric environment and analyze their data to understand the forecasting scenario.

## Prerequisites

- User has access to a Microsoft Fabric workspace
- User has data in a Lakehouse table (or knows where to put it)
- Agent file `time-series-forecaster.md` provides persona and boundaries

## Phase 0: Gather Required Inputs

If the user has not provided all required inputs, present this prompt:

```
🔮 **Time Series Forecasting Accelerator**

I'll help you customize the forecasting pipeline for your specific dataset and scenario.

To get started, I need:

1. **Fabric Workspace**: Which workspace contains your data?
2. **Lakehouse Name**: Which Lakehouse has your time series data?
3. **Table Name(s)**: What table(s) contain your historical data?
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

## Phase 1.1: Connect to Fabric

Once required inputs are received:

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

## Phase 1.2: Analyze Data Schema

Query the data to understand its structure:

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

**Source:** <workspace_name>.<lakehouse_name>.<table_name>

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

### Workspace/Lakehouse Not Found
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

Table "<table_name>" was not found in <lakehouse_name>.

Available tables:
<list tables from INFORMATION_SCHEMA.TABLES>

Please provide the correct table name.
```

### SQL Query Errors
- Analyze the error message
- Adjust query syntax for Fabric SQL endpoint
- Retry with corrected query

## Outputs for Next Phase

After user confirms the data profile, pass these to Phase 2:

- **workspace_name**: Confirmed workspace
- **workspace_id**: For Livy session creation
- **lakehouse_name**: Confirmed lakehouse
- **lakehouse_id**: For Livy session creation
- **table_name**: Confirmed table(s)
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
3. Fill the **Phase 1: Data Discovery** section with all gathered data
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
