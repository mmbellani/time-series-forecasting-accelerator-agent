# Phase 5: Finalization & Delivery

Assemble output artifacts, optionally upload notebooks to Fabric, archive existing tables, execute the pipeline, and deliver the customized solution.

## Prerequisites

- Phase 4 completed: All 5 notebooks generated and validated
- **Completion report** from Phase 4 (user provides path)

## Phase Start — Read Completion Report

At the start of this phase:
1. Read the completion report from the path provided by user
2. The report now contains all context from Phases 1-4
3. Use this for generating final deliverables and Fabric deployment

### Context from Prior Phases (via completion report):
  - output_folder: Path containing all 5 notebooks
  - workspace_name, workspace_id: Fabric workspace (from Phase 1)
  - lakehouse_name, lakehouse_id: Fabric lakehouse (from Phase 1)
  - scenario_name: Derived scenario name (from Phase 2)
  - validation_results: Per-notebook validation status (from Phase 4)
  - output_tables: Table names created by each notebook (from Phase 4)
  - errors_log: All errors encountered and resolutions
  - new_dependencies: Packages to add to requirements.txt

---

## Step 1: Verify Output Folder Contents

Confirm all 5 notebooks exist in the output folder:

```
<output_folder>/
├── Fabric 01 DataPreparation.ipynb
├── Fabric 02 ExploratoryDataAnalysis.ipynb
├── Fabric 03 ProfilingIntermittent.ipynb
├── Fabric 04 Clustering.ipynb
├── Fabric 05 FeatureEngineering.ipynb
└── Fabric 06 TrainTestSelectTune.ipynb
```

If any notebook is missing, stop and report the issue to the user.

---

## Step 2: Generate requirements.txt (If Needed)

If new dependencies were introduced, create `requirements.txt`:

```
# Requirements for <scenario_name>
# Generated: <YYYY-MM-DD>
#
# These packages are in addition to the standard Fabric environment.
# Install via: %pip install -r requirements.txt

<package1>==<version>
<package2>>=<min_version>
...
```

**Note:** Only include packages NOT already in the standard Fabric environment.

---

## Step 3: Offer Upload to Fabric

Present the upload option to the user:

```
📤 **Upload to Fabric?**

Your 5 customized notebooks are ready locally. Would you like me to upload them to your Fabric workspace?

**Target Workspace:** <workspace_name>
**Lakehouse to Attach:** <lakehouse_name>

Options:
A) Yes, upload notebooks to Fabric
B) No, keep notebooks local only — I'll upload manually
```

Wait for user response.

### If User Chooses B (Skip Upload)
- Proceed directly to [Step 7: Finalize Completion Report](#step-7-finalize-completion-report)
- Update completion report: Upload Status = "⏭️ Skipped by user"

### If User Chooses A (Upload)
- Continue to Step 4

---

## Step 4: Upload Notebooks to Fabric

### 4.1 Check for Existing Notebooks

Query the workspace for existing notebooks:

```python
list_items(workspace_name=<workspace_name>, item_type="Notebook")
```

Check if any of these notebooks already exist:
- `Fabric 01 DataPreparation`
- `Fabric 02 ExploratoryDataAnalysis`
- `Fabric 03 ProfilingIntermittent`
- `Fabric 04 Clustering`
- `Fabric 05 FeatureEngineering`
- `Fabric 06 TrainTestSelectTune`

### 4.2 Confirm Delete and Re-upload (If Needed)

If any notebooks already exist, present confirmation:

```
⚠️ **Existing Notebooks Found**

The following notebooks already exist in workspace "<workspace_name>":

| Notebook | Status |
|----------|--------|
| Fabric 01 DataPreparation | ⚠️ Exists |
| Fabric 02 ExploratoryDataAnalysis | ⚠️ Exists |
| Fabric 03 ProfilingIntermittent | ⚠️ Exists |
| Fabric 04 Clustering | New |
| Fabric 05 FeatureEngineering | ⚠️ Exists |
| Fabric 06 TrainTestSelectTune | New |

I will need to **delete** the existing notebooks and then **re-upload** them. Continue? (Y/N)
```

- If user declines → Skip upload, proceed to Step 7
- If user confirms → Continue with deletion and upload

### 4.3 Delete Existing Notebooks (If Any)

For each existing notebook, delete it using `delete_item()`:

```python
delete_item(
    workspace_name=<workspace_name>,
    item_display_name="Fabric 01 DataPreparation",
    item_type="Notebook"
)
```

Delete all existing notebooks (can be done in parallel).

**Important:** After deleting notebooks, **wait 2 minutes** before uploading. Fabric requires time to release the notebook names for reuse. Use `sleep 120` in the terminal to pause.

### 4.4 Upload All Notebooks

For each notebook, call `import_notebook_to_fabric()`:

```python
import_notebook_to_fabric(
    workspace_name=<workspace_name>,
    notebook_display_name="Fabric 01 DataPreparation",  # No subfolder, root level
    local_notebook_path="<output_folder>/Fabric 01 DataPreparation.ipynb",
    description="Time Series Forecasting - <scenario_name> - Generated <YYYY-MM-DD>"
)
```

Upload all 5 notebooks (can be done in parallel).

### 4.5 Attach Lakehouse to All Notebooks

After all uploads complete, attach the lakehouse to each notebook:

```python
attach_lakehouse_to_notebook(
    workspace_name=<workspace_name>,
    notebook_name="Fabric 01 DataPreparation",
    lakehouse_name=<lakehouse_name>
)
```

Attach lakehouse to all 5 notebooks (can be done in parallel).

### 4.6 Report Upload Success

```
✅ **Notebooks Uploaded Successfully**

| Notebook | Upload | Lakehouse |
|----------|--------|-----------|
| Fabric 01 DataPreparation | ✅ Uploaded | ✅ Attached |
| Fabric 02 ExploratoryDataAnalysis | ✅ Uploaded | ✅ Attached |
| Fabric 03 ProfilingIntermittent | ✅ Uploaded | ✅ Attached |
| Fabric 04 Clustering | ✅ Uploaded | ✅ Attached |
| Fabric 05 FeatureEngineering | ✅ Uploaded | ✅ Attached |
| Fabric 06 TrainTestSelectTune | ✅ Uploaded | ✅ Attached |
```

---

## Step 5: Offer Pipeline Execution

After successful upload, offer execution:

```
🚀 **Execute Notebooks?**

Notebooks are now in Fabric. Would you like me to run the full pipeline?

⚠️ **Note:** If output tables already exist from a previous run, they will be 
archived with an `archive_` prefix before execution (e.g., `df_final` → `archive_df_final`).

Options:
A) Yes, archive existing tables and execute the pipeline
B) No, I'll run the notebooks manually later
```

Wait for user response.

### If User Chooses B (Skip Execution)
- Proceed directly to [Step 7: Finalize Completion Report](#step-7-finalize-completion-report)
- Update completion report: Execution Status = "⏭️ Skipped by user"

### If User Chooses A (Execute)
- Continue to Step 6

---

## Step 6: Archive Tables and Execute Pipeline

**IMPORTANT:** 
- Use **Livy sessions** ONLY for table archiving operations (Steps 6.1-6.4)
- Use **`run_on_demand_job`** for notebook execution (Step 6.5) — NEVER execute notebooks via Livy

### 6.1 Prepare Livy Session (For Archiving Only)

Follow the standard Livy session management rules:

1. Check for existing sessions: `livy_list_sessions(workspace_id, lakehouse_id)`
2. If idle session exists → Reuse it
3. If no session exists → Create new session:
   ```python
   livy_create_session(workspace_id, lakehouse_id, kind="pyspark", with_wait=True)
   ```

**Note:** This session is used ONLY for checking/archiving tables, NOT for running notebooks.

### 6.2 Check for Existing Archive Tables

Before archiving, check if `archive_*` tables already exist. Execute via Livy:

```python
code = """
tables = spark.catalog.listTables()
archive_tables = [t.name for t in tables if t.name.startswith('archive_')]
print(archive_tables)
"""
livy_run_statement(workspace_id, lakehouse_id, session_id, code)
```

### 6.3 Handle Existing Archives

If archive tables exist, present options:

```
⚠️ **Existing Archive Tables Found**

Archive tables from a previous run already exist:

| Archive Table | Action Needed |
|---------------|---------------|
| archive_df_final | ⚠️ Exists |
| archive_df_profiling | ⚠️ Exists |
| archive_df_profiling_cluster | New |
| archive_df_features | New |
| archive_<scenario>_forecasts | ⚠️ Exists |

Options:
A) Delete existing archives and proceed with new archiving
B) Cancel execution — I'll handle archives manually
```

- If user chooses B → Skip execution, proceed to Step 7
- If user chooses A → Drop existing archives first:

```python
code = """
spark.sql("DROP TABLE IF EXISTS lakehouse.archive_df_final")
spark.sql("DROP TABLE IF EXISTS lakehouse.archive_df_profiling")
# ... repeat for each existing archive
"""
livy_run_statement(workspace_id, lakehouse_id, session_id, code)
```

### 6.4 Archive Current Tables

For each output table (read from completion report Phase 4), rename to archive:

| Original Table | Archived As |
|----------------|-------------|
| `df_final` | `archive_df_final` |
| `df_profiling` | `archive_df_profiling` |
| `df_profiling_cluster` | `archive_df_profiling_cluster` |
| `df_features` | `archive_df_features` |
| `<scenario>_forecasts` | `archive_<scenario>_forecasts` |

Execute via Livy:

```python
code = """
# Check if table exists before renaming
tables = [t.name for t in spark.catalog.listTables()]

if 'df_final' in tables:
    spark.sql("ALTER TABLE lakehouse.df_final RENAME TO lakehouse.archive_df_final")
    print("Archived: df_final → archive_df_final")
else:
    print("Skipped: df_final (does not exist)")

# Repeat for each table...
"""
livy_run_statement(workspace_id, lakehouse_id, session_id, code)
```

**Note:** If a table doesn't exist (e.g., first run), skip silently — no error.

### 6.5 Execute Notebooks Sequentially (via run_on_demand_job)

**CRITICAL:** Always use `run_on_demand_job()` to execute notebooks — NEVER use Livy sessions for notebook execution.

```
🚀 **Pipeline Execution Started**

| Notebook | Status | Duration |
|----------|--------|----------|
| 01 DataPreparation | 🔄 Running... | - |
| 02 ExploratoryDataAnalysis | ⏳ Pending | - |
| 03 ProfilingIntermittent | ⏳ Pending | - |
| 04 Clustering | ⏳ Pending | - |
| 05 FeatureEngineering | ⏳ Pending | - |
| 06 TrainTestSelectTune | ⏳ Pending | - |
```

For each notebook (01 → 02 → 03 → 04 → 05 → 06):

1. **Start the job:**
   ```python
   result = run_on_demand_job(
       workspace_name=<workspace_name>,
       item_name="Fabric 01 DataPreparation",
       item_type="Notebook",
       job_type="RunNotebook"
   )
   job_instance_id = result["job_instance_id"]
   location_url = result["location_url"]
   ```

2. **Poll for completion** (every 30 seconds):
   ```python
   status = get_job_status_by_url(location_url)
   # Check status["job"]["is_terminal"]
   # If is_successful → Continue to next notebook
   # If is_failed → Enter failure recovery
   ```

3. **Update progress display** after each notebook completes

4. **On success:** Log job_instance_id, duration, continue to next notebook

5. **On failure:** Enter [Failure Recovery](#failure-recovery) flow

### 6.6 Execution Complete

When all 5 notebooks complete successfully:

```
✅ **Pipeline Execution Complete!**

| Notebook | Status | Job ID | Duration |
|----------|--------|--------|----------|
| 01 DataPreparation | ✅ Complete | abc-123 | 3m 12s |
| 02 ExploratoryDataAnalysis | ✅ Complete | bcd-234 | 2m 30s |
| 03 ProfilingIntermittent | ✅ Complete | def-456 | 2m 05s |
| 04 Clustering | ✅ Complete | ghi-789 | 4m 18s |
| 05 FeatureEngineering | ✅ Complete | jkl-012 | 2m 44s |
| 06 TrainTestSelectTune | ✅ Complete | pqr-678 | 3m 03s |

**Total Duration:** 15m 22s

📊 Your forecasts are ready in table: `<scenario>_forecasts`
```

---

## Failure Recovery

When a notebook fails during execution, follow this recovery protocol.

### Step F1: Retrieve Error Details

Fetch driver logs to understand the failure:

```python
logs = get_notebook_driver_logs(
    workspace_name=<workspace_name>,
    notebook_name="Fabric 04 Clustering",  # Failed notebook
    job_instance_id=<job_instance_id>,
    log_type="stdout",  # Python exceptions are in stdout!
    max_lines=500
)
```

**Important:** Python errors and tracebacks appear in `stdout`, not `stderr`.

### Step F2: Present Error to User

```
❌ **Execution Failed at Notebook 04 (Clustering)**

**Error:**
```
KeyError: 'cluster_id' - Column not found in DataFrame
  at Cell 7: df_clustered = df.select('unique_id', 'cluster_id', 'profile')
```

**Analysis:**
The column 'cluster_id' was expected but not created. This may be due to:
- K-Means clustering step producing different output column names
- Empty DataFrame after filtering for 'regular' profiles

**Options:**
A) Let me fix the notebook and re-run
B) Show me the full error logs
C) Stop here — I'll fix it manually in Fabric
```

### Step F3: Handle User Response

#### Option A: Agent-Assisted Fix

1. **Analyze root cause** to determine which notebook needs fixing:
   - If error is in current notebook → Fix current notebook
   - If error stems from upstream notebook → Fix the upstream notebook

2. **Determine restart point:**
   - If fix was in NB04 → Restart from NB04, continue to NB05, NB06
   - If fix was in NB01 → Restart from NB01, re-run NB01 → NB02 → NB03 → NB04 → NB05 → NB06

3. **Apply fix:**
   - Read the notebook from local output folder
   - Apply the fix to the relevant cell
   - Save the updated notebook locally
   - Re-upload the fixed notebook to Fabric:
     ```python
     import_notebook_to_fabric(
         workspace_name=<workspace_name>,
         notebook_display_name="Fabric 04 Clustering",
         local_notebook_path="<output_folder>/Fabric 04 Clustering.ipynb"
     )
     attach_lakehouse_to_notebook(
         workspace_name=<workspace_name>,
         notebook_name="Fabric 04 Clustering",
         lakehouse_name=<lakehouse_name>
     )
     ```

4. **Re-execute from restart point:**
   - Tables are already archived, no need to re-archive
   - Resume sequential execution from the determined restart point

5. **Retry limit:**
   - Maximum 3 fix attempts per failure
   - After 3 failed attempts, escalate with option C

#### Option B: Full Logs

Retrieve complete logs:

```python
logs = get_notebook_driver_logs(
    workspace_name=<workspace_name>,
    notebook_name="Fabric 04 Clustering",
    job_instance_id=<job_instance_id>,
    log_type="stdout",
    max_lines=None  # Get all lines
)
```

Present full logs to user, then re-offer options A or C.

#### Option C: Manual Resolution

Stop execution and proceed to Step 7 with partial status:
- Update completion report with execution details
- Document the error and failed notebook
- Note which notebooks completed successfully

---

## Step 7: Finalize Completion Report

Update the completion report with Phase 5 results:

1. **Update Status section** — Mark Phase 5 as `[x]` complete
2. **Update metadata** — Set "Last Updated" to current date with "(Phase 5)"
3. **Fill Phase 5 section:**
   - Notebook Upload status and details
   - Table Archiving status (if executed)
   - Pipeline Execution status (if executed)
   - Per-notebook execution details with job IDs and durations
   - Any errors encountered and resolutions
4. **Add Warnings & Recommendations** based on findings
5. **Verify all prior phase sections** are complete

---

## Checkpoint 5.1: Present Final Summary

Present a summary tailored to what actions were taken:

### Scenario A: Full Execution (Upload + Execute)

```
🎉 **Pipeline Customization & Execution Complete!**

---

### 📤 Upload Summary
| Attribute | Value |
|-----------|-------|
| Workspace | <workspace_name> |
| Notebooks Uploaded | 5 |
| Lakehouse Attached | <lakehouse_name> |

### 🗄️ Archiving Summary
| Original Table | Archived As | Status |
|----------------|-------------|--------|
| df_final | archive_df_final | ✅ Archived |
| df_profiling | archive_df_profiling | ✅ Archived |
| df_profiling_cluster | archive_df_profiling_cluster | ⏭️ Did not exist |
| df_features | archive_df_features | ✅ Archived |
| <scenario>_forecasts | archive_<scenario>_forecasts | ✅ Archived |

### 🚀 Execution Summary
| Notebook | Status | Duration |
|----------|--------|----------|
| 01 DataPreparation | ✅ | 3m 12s |
| 02 Profiling | ✅ | 2m 05s |
| 03 Clustering | ✅ | 4m 18s |
| 04 FeatureEngineering | ✅ | 2m 44s |
| 05 TrainTestSelectTune | ✅ | 3m 03s |

**Total Pipeline Duration:** 15m 22s

📊 **Your forecasts are ready in table:** `<scenario>_forecasts`

---

**Full details:** `<output_folder>/completion_report.md`
```

### Scenario B: Upload Only (No Execution)

```
✅ **Notebooks Uploaded to Fabric**

| Attribute | Value |
|-----------|-------|
| Workspace | <workspace_name> |
| Notebooks Uploaded | 5 |
| Lakehouse Attached | <lakehouse_name> |
| Execution | ⏭️ Skipped (run manually when ready) |

**To run the pipeline manually:**
1. Open Fabric workspace "<workspace_name>"
2. Run notebooks in order: 01 → 02 → 03 → 04 → 05

---

**Full details:** `<output_folder>/completion_report.md`
```

### Scenario C: Local Only (No Upload)

```
✅ **Customization Complete — Local Delivery**

Your customized notebooks are ready at:
`<output_folder>/`

| File | Status |
|------|--------|
| Fabric 01 DataPreparation.ipynb | ✅ Ready |
| Fabric 02 ExploratoryDataAnalysis.ipynb | ✅ Ready |
| Fabric 03 ProfilingIntermittent.ipynb | ✅ Ready |
| Fabric 04 Clustering.ipynb | ✅ Ready |
| Fabric 05 FeatureEngineering.ipynb | ✅ Ready |
| Fabric 06 TrainTestSelectTune.ipynb | ✅ Ready |
| completion_report.md | ✅ Generated |
| requirements.txt | <Included / Not needed> |

**To deploy manually:**
1. Import notebooks to your Fabric workspace
2. Attach lakehouse "<lakehouse_name>" to each notebook
3. Run notebooks in order: 01 → 02 → 03 → 04 → 05

---

**Full details:** `<output_folder>/completion_report.md`
```

---

## Post-Delivery Support

Checkpoint protocol (hard stop):
1. Log this checkpoint as **Pending** in `completion_report.md` (Checkpoint Log), including:
   - phase: `5`
   - notebook: (none)
   - cell index / step: `Checkpoint 5.1`
   - raw checkpoint text: the summary presented
   - questions asked: the Post-Delivery Support options prompt
   - answers: leave blank until user responds
2. Stop and wait for the user to select an option and type `continue`.
3. On `continue`, update the same checkpoint entry with the user’s choice and mark it completed, then STOP. If the user wants A/B support, they start a new chat and restate the desired option (A/B) with the completion report path.

After presenting the summary, offer follow-up options:

```
Would you like me to:
A) Walk through the completion report
B) Explain any specific customization
C) That's all — thank you!

Reply with your choice, then type `continue` to record this checkpoint. If you choose A or B, start a new chat and restate the same choice (A/B) with the completion report path.
```

### A) Walk through completion report
- Summarize each section
- Highlight key decisions and rationale
- Explain any warnings in detail

### B) Explain specific customization
- Refer to the relevant notebook section
- Show the before/after code
- Explain the rationale

### C) Session complete

```
✅ **Session Complete**

Thank you for using the Time Series Forecaster!

Your customized pipeline is in:
`<output_folder>/`

If you need to customize another scenario, just start a new conversation.

Happy forecasting! 📈
```

---

## Error Handling

### Missing Notebooks (Step 1)
If any notebook is missing from output folder:
- Check Phase 4 for errors
- Report the issue to user with guidance to re-run Phase 4

### Upload Failures (Step 4)
If notebook upload fails:
- Retry once
- If still failing, report error and skip to local-only delivery
- Document in completion report

### Archiving Failures (Step 6)
If table archiving fails:
- Check if table actually exists (might be first run)
- If table exists but rename fails, report error and offer options

### Execution Failures (Step 6)
- Follow the [Failure Recovery](#failure-recovery) protocol
- After 3 failed fix attempts, stop and document partial results

---

## Outputs

Final deliverables in `<output_folder>/`:

| Artifact | Required | Description |
|----------|----------|-------------|
| `Fabric 01 DataPreparation.ipynb` | ✅ | Customized notebook |
| `Fabric 02 ExploratoryDataAnalysis.ipynb` | ✅ | Customized notebook |
| `Fabric 03 ProfilingIntermittent.ipynb` | ✅ | Customized notebook |
| `Fabric 04 Clustering.ipynb` | ✅ | Customized notebook |
| `Fabric 05 FeatureEngineering.ipynb` | ✅ | Customized notebook |
| `Fabric 06 TrainTestSelectTune.ipynb` | ✅ | Customized notebook |
| `completion_report.md` | ✅ | Full documentation |
| `requirements.txt` | ❓ | Only if new dependencies |

---

## Workflow Complete

```
✅ Time Series Forecaster Workflow Complete

Phase 1: Intake & Discovery .......... ✅
Phase 2: Scenario Interpretation ..... ✅
Phase 3: Customization Planning ...... ✅
Phase 4: Notebook Generation ......... ✅
Phase 5: Finalization & Delivery ..... ✅
         ├─ Upload to Fabric ........ <✅/⏭️>
         ├─ Table Archiving ......... <✅/⏭️>
         └─ Pipeline Execution ...... <✅/⏭️>

Output: <output_folder>/
```
