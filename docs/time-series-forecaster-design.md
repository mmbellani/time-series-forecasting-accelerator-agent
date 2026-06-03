# Time Series Forecaster Agent — Design Document

**Version:** 1.0  
**Date:** November 29, 2025  
**Status:** Draft

---

## Table of Contents

1. [Overview & Purpose](#1-overview--purpose)
2. [Workflow Phases & Checkpoints](#2-workflow-phases--checkpoints)
3. [Tools & Capabilities](#3-tools--capabilities)
4. [Customization Dimensions](#4-customization-dimensions)
5. [Output Artifacts](#5-output-artifacts)
6. [Error Handling](#6-error-handling)
7. [Boundaries & Guardrails](#7-boundaries--guardrails)
8. [Prompt File Structure](#8-prompt-file-structure)
9. [Agent Implementation Guide](#9-agent-implementation-guide)

---

## 1. Overview & Purpose

The **`time-series-forecaster`** agent is a custom AI assistant that helps data scientists customize the Time Series Forecasting Accelerator pipeline for their specific datasets and scenarios. Rather than manually adapting the 5-notebook pipeline (Data Preparation → Profiling → Clustering → Feature Engineering → Train/Tune), users describe their forecasting scenario and point to their data in a Fabric Lakehouse, and the agent handles the rest.

### Core Value Proposition

- **Reduces time-to-forecast** by automating notebook customization
- **Ensures correctness** by validating all generated code via Livy sessions before delivery
- **Maintains control** by requiring data scientist approval at key checkpoints
- **Documents everything** in a completion report for reproducibility and audit

### How It Works (High-Level)

1. **Agent prompts for required inputs** — If user hasn't provided Lakehouse table reference and scenario description, agent explicitly asks for them before proceeding
2. Agent analyzes the data (schema, profiles, statistics) and asks clarifying questions
3. Agent proposes customizations for each notebook, explaining rationale
4. Upon approval, agent generates and validates each notebook using Livy
5. Agent delivers a timestamped folder containing 5 customized notebooks, a completion report, and requirements.txt (if needed)

### Key Design Principles

- **No assumptions**: Agent never proceeds without required inputs; always prompts explicitly
- **Graduated autonomy**: Simple changes proceed with light approval; structural/generative changes require explicit sign-off
- **Phase-based checkpoints**: Workflow divided into phases with approval gates codified in prompts
- **Preserve structure**: 5-notebook architecture maintained unless deviation is justified and approved

---

## 2. Workflow Phases & Checkpoints

The agent workflow is divided into distinct phases, each with explicit checkpoints where the agent pauses for user approval. Sub-phase checkpoints are permitted when the agent determines additional confirmation is warranted (e.g., before a high-risk customization).

### Phase 1: Intake & Data Discovery

- **Checkpoint 1.1**: Confirm required inputs received (Lakehouse workspace, table name(s), scenario description)
- Agent connects to Fabric, analyzes the data: schema, row counts, time range, series count, null rates, value distributions
- Agent presents data profile summary to user
- **Checkpoint 1.2**: User confirms data understanding is correct

### Phase 2: Scenario Interpretation

- Agent interprets the scenario description and infers customization parameters:
  - Time granularity (daily/weekly/monthly)
  - Forecast horizon
  - Hierarchy structure (single/multi-series/hierarchical)
  - Seasonality patterns
  - External regressors (if any)
  - Industry-specific considerations
  - Model preferences
  - Evaluation criteria
- Agent presents its interpretation with rationale for each inference
- **Checkpoint 2.1**: User approves or corrects the interpretation

### Phase 3: Customization Planning

- Agent generates a customization plan for each of the 5 notebooks
- Plan specifies: parameters to change, cells to modify/add/remove, new logic to introduce
- Each change is tagged with risk level (low/medium/high)
- **Checkpoint 3.1**: User approves the overall plan (or iterates)

### Phase 4: Notebook Generation & Validation

- For each notebook (01 → 05):
  - Agent generates the customized notebook
  - Agent validates code cells via Livy session
  - If errors occur: auto-retry with fixes (up to 3 attempts), then escalate
  - **Checkpoint 4.N** (optional): For high-risk notebooks, pause for approval before proceeding to next

### Phase 5: Finalization & Delivery

- Agent assembles output folder (timestamped)
- Agent generates completion report (≤5000 words)
- Agent generates requirements.txt if new dependencies were introduced
- **Checkpoint 5.1**: Agent presents summary and output location; user confirms receipt

---

## 3. Tools & Capabilities

The agent uses Microsoft Fabric MCP tools to interact with the target platform. This section provides guidance on which tools to use for each workflow task.

### Workspace & Data Discovery

| Task | Tool(s) |
|------|---------|
| List available workspaces | `list_workspaces()` |
| Find Lakehouses in a workspace | `list_items(workspace_name, item_type="Lakehouse")` |
| Get SQL endpoint for querying | `get_sql_endpoint(workspace_name, item_name, item_type)` |
| Query table schema & statistics | `execute_sql_query(sql_endpoint, query, database)` |

### Livy Session Management (for code validation)

| Task | Tool(s) |
|------|---------|
| List existing sessions | `livy_list_sessions(workspace_id, lakehouse_id)` |
| Create a Spark session | `livy_create_session(workspace_id, lakehouse_id, kind="pyspark", with_wait=True)` |
| Check session readiness | `livy_get_session_status(workspace_id, lakehouse_id, session_id)` |
| Execute/validate code cells | `livy_run_statement(workspace_id, lakehouse_id, session_id, code, with_wait=True)` |
| Retrieve session logs (debugging) | `livy_get_session_log(workspace_id, lakehouse_id, session_id)` |
| Close session (optional) | `livy_close_session(workspace_id, lakehouse_id, session_id)` |

### Key Rules

1. **Never finalize notebook code without Livy validation** — All code cells must be executed via `livy_run_statement()` before being included in the final notebook
2. **Reuse existing Livy sessions** — Before creating a new session, check for existing idle sessions using `livy_list_sessions()` and `livy_get_session_status()`. Reuse if available.
3. **Keep sessions open between phases** — Since there may be time gaps between workflow stages (waiting for user approval), leave sessions open for reuse rather than closing after each phase
4. **Use SQL for simple data profiling** — Prefer `execute_sql_query()` for schema/stats discovery (faster than Spark for simple queries)
5. **Use Livy for complex data analysis** — When profiling requires Spark operations (e.g., time series patterns, distributions), use Livy sessions
6. **Close session only at workflow end** — Call `livy_close_session()` only when the entire workflow is complete or explicitly requested by the user

---

## 4. Customization Dimensions

The agent can customize the pipeline across multiple dimensions. Each customization requires the agent to **explain its rationale** and **obtain user approval** before proceeding. Customizations are categorized by risk level, which determines how cautiously the agent should proceed.

### Low Risk (Parameter Substitution)

These changes update values without altering notebook structure or logic.

- Column name mappings (date column, target column, ID columns)
- Table names (input/output Lakehouse tables)
- Forecast horizon (e.g., 4 weeks, 12 months)
- Date parsing formats
- Train/test split ratios

### Medium Risk (Structural Adaptation)

These changes modify cells, add/remove logic, or adjust the flow within a notebook.

- Time granularity adjustments (daily → weekly aggregation logic)
- Lag and rolling window sizes (based on seasonality)
- Feature selection (add/remove calendar features, rolling stats)
- Clustering parameters (number of clusters, algorithm settings)
- Profiling thresholds (CV², ADI cutoffs for classification)
- Skip/simplify sections (e.g., skip clustering for single-series)

### High Risk (Algorithm/Generative Changes)

These changes introduce new logic, swap algorithms, or create cells not in the original templates.

- Model selection changes (add ARIMA, switch to XGBoost, ensemble methods)
- External regressor integration (promotions, holidays, weather)
- Industry-specific logic (retail stockout handling, financial business-day calendars)
- Hierarchy handling (reconciliation logic for hierarchical forecasts)
- Custom evaluation metrics or visualizations
- New cells with domain-specific preprocessing

### Risk-Based Behavior

| Risk Level | Agent Behavior |
|------------|----------------|
| Low | Propose change with brief rationale; proceed after acknowledgment |
| Medium | Explain rationale in detail; wait for explicit approval |
| High | Present alternatives if applicable; require explicit approval; flag in completion report |

---

## 5. Output Artifacts

The agent produces a timestamped project folder containing all deliverables. The folder naming convention is:

```
.output/<scenario_name>_<YYYYMMDD>/
```

For example: `.output/retail_weekly_forecast_20251129/`

### Folder Contents

| Artifact | Description |
|----------|-------------|
| `Fabric 01 DataPreparation.ipynb` | Customized data preparation notebook |
| `Fabric 02 ExploratoryDataAnalysis.ipynb` | Customized EDA notebook |
| `Fabric 03 ProfilingIntermittent.ipynb` | Customized profiling notebook |
| `Fabric 04 Clustering.ipynb` | Customized clustering notebook |
| `Fabric 05 FeatureEngineering.ipynb` | Customized feature engineering notebook |
| `Fabric 06 TrainTestSelectTune.ipynb` | Customized training/tuning notebook |
| `completion_report.md` | Summary of the customization process |
| `requirements.txt` | Additional dependencies (only if new packages were introduced) |

### Completion Report Structure (≤5000 words)

1. **Scenario Summary** — User's original request and agent's interpretation
2. **Data Profile** — Key statistics: row count, time range, series count, granularity, data quality issues discovered
3. **Customization Decisions** — Each parameter/structural change with rationale, organized by notebook
4. **Notebook-by-Notebook Changes** — Concise summary of what was modified vs. the original template
5. **Validation Results** — Livy session outcomes; any errors encountered and how they were resolved
6. **Warnings & Recommendations** — Issues the data scientist should monitor (e.g., "15% of series are intermittent—consider alternative methods")
7. **Next Steps** — Instructions for uploading and executing the notebooks in Fabric

### Notebook Conventions

- Each notebook includes a header cell documenting: scenario name, generation date, key parameters
- Inline comments explain customizations where they differ from the template
- All code validated via Livy before inclusion

---

## 6. Error Handling

The agent follows an **auto-retry with escalation** strategy when errors occur during Livy validation. This keeps the workflow moving while ensuring the user is involved when issues can't be resolved automatically.

### Error Categories & Responses

| Error Type | Examples | Agent Response |
|------------|----------|----------------|
| **Syntax errors** | Missing parentheses, indentation issues, typos | Auto-fix and retry (up to 3 attempts) |
| **Import errors** | Missing packages, wrong module names | Add to requirements.txt, adjust import, retry |
| **Data errors** | Column not found, type mismatch, null handling | Analyze schema, adjust code, retry |
| **Logic errors** | Incorrect aggregation, wrong join keys | Attempt diagnosis and fix; escalate if unclear |
| **Resource errors** | Session timeout, Spark memory issues | Retry with session refresh; escalate if persistent |
| **Unresolvable errors** | Ambiguous requirements, conflicting logic | Stop and escalate to user immediately |

### Retry Protocol

1. **Attempt 1**: Execute code via `livy_run_statement()`
2. **On failure**: Analyze error message, diagnose root cause, apply fix
3. **Attempt 2**: Re-execute with fix
4. **On failure**: Try alternative approach if applicable
5. **Attempt 3**: Final attempt with alternative
6. **On failure**: Escalate to user with:
   - Original code
   - Error message
   - Attempted fixes and their outcomes
   - Request for guidance

### Escalation Format

```
⚠️ **Validation Error — User Input Required**

**Notebook:** Fabric 04 Clustering.ipynb
**Cell:** [description of cell purpose]

**Error:**
[error message]

**Attempted Fixes:**
1. [fix 1] → [outcome]
2. [fix 2] → [outcome]

**Options:**
A) [suggested alternative approach]
B) Skip this cell and continue
C) Provide guidance

How would you like to proceed?
```

### Logging

- All errors and resolution attempts are logged in the completion report
- Escalated issues are flagged prominently in the Warnings section

---

## 7. Boundaries & Guardrails

The agent operates within clear boundaries to ensure safe, predictable behavior. These are categorized into what the agent should always do, what requires permission, and what it should never do.

### ✅ Always Do

- Prompt for required inputs (workspace, lakehouse, table, scenario) before starting
- Read and understand template notebooks before generating customizations
- Validate all code cells via Livy before including in final notebooks
- Explain rationale for every customization decision
- Obtain user approval at phase checkpoints
- Preserve the 5-notebook structure unless deviation is approved
- Document all decisions, errors, and resolutions in the completion report
- Use existing Livy sessions when available
- Generate outputs in timestamped folders (never overwrite templates)

### ⚠️ Ask First

- Structural changes to notebooks (adding/removing cells, changing flow)
- Algorithm or model changes (swapping LightGBM for another model)
- Introducing new dependencies (packages not in original requirements)
- Skipping entire notebooks or major sections
- Deviating from the 5-notebook structure (merging or splitting)
- Creating generative/novel logic not in templates
- Any high-risk customization as defined in Section 4

### 🚫 Never Do

- Proceed without required inputs (workspace, table, scenario)
- Save notebook code that hasn't been validated via Livy
- Overwrite or modify the original template notebooks in `src/notebooks/`
- Hardcode credentials, connection strings, or secrets
- Make assumptions about column names or data structure without verification
- Skip user approval for medium or high-risk changes
- Execute the final pipeline in Fabric (generation + validation only)
- Delete user data or existing Lakehouse tables
- Close Livy sessions without completing the current phase (unless requested)

---

## 8. Prompt File Structure

The agent workflow is codified in prompt files that define each phase's behavior and checkpoints. Each prompt explicitly references the template notebooks relevant to that phase.

### Proposed Prompt Files

| Prompt File | Phase | Notebook References |
|-------------|-------|---------------------|
| `tsf-01-intake-discovery.prompt.md` | Phase 1 | None (data analysis only) |
| `tsf-02-scenario-interpretation.prompt.md` | Phase 2 | All 5 notebooks (to understand customization scope) |
| `tsf-03-customization-planning.prompt.md` | Phase 3 | All 5 notebooks (to generate per-notebook plans) |
| `tsf-04-notebook-generation.prompt.md` | Phase 4 | All 5 notebooks (one-by-one generation & validation) |
| `tsf-05-finalization.prompt.md` | Phase 5 | None (output assembly only) |

### Notebook References in Prompts

Each prompt that operates on notebooks includes a **Notebook References** section:

| Notebook | Path | Purpose |
|----------|------|---------|
| 01 Data Preparation | `src/notebooks/Fabric 01 DataPreparation.ipynb` | Clean data, fill time gaps |
| 02 EDA | `src/notebooks/Fabric 02 ExploratoryDataAnalysis.ipynb` | Summary statistics, visualizations |
| 03 Profiling | `src/notebooks/Fabric 03 ProfilingIntermittent.ipynb` | Classify series (regular, lumpy, erratic, etc.) |
| 04 Clustering | `src/notebooks/Fabric 04 Clustering.ipynb` | Group similar series with K-Means |
| 05 Feature Engineering | `src/notebooks/Fabric 05 FeatureEngineering.ipynb` | Create lags, rolling stats, calendar features |
| 06 Train/Tune | `src/notebooks/Fabric 06 TrainTestSelectTune.ipynb` | Train LightGBM, tune with Optuna |

### Prompt 4 (Notebook Generation) — Detailed Structure

Since Phase 4 is the core generation phase, it includes per-notebook sections:

#### Notebook 01: Data Preparation
- **Template:** `src/notebooks/Fabric 01 DataPreparation.ipynb`
- **Key customizations:** Column mappings, date parsing, table names
- **Validation focus:** Data loads correctly, schema matches expectations

#### Notebook 03: Profiling
- **Template:** `src/notebooks/Fabric 03 ProfilingIntermittent.ipynb`
- **Key customizations:** Profiling thresholds, classification logic
- **Validation focus:** Profiles compute without error

#### Notebook 04: Clustering
- **Template:** `src/notebooks/Fabric 04 Clustering.ipynb`
- **Key customizations:** Cluster count, algorithm parameters, skip logic
- **Validation focus:** Clustering executes, labels assigned

#### Notebook 05: Feature Engineering
- **Template:** `src/notebooks/Fabric 05 FeatureEngineering.ipynb`
- **Key customizations:** Lag windows, rolling stats, calendar features, external regressors
- **Validation focus:** Feature matrix generates correctly

#### Notebook 06: Train/Tune
- **Template:** `src/notebooks/Fabric 06 TrainTestSelectTune.ipynb`
- **Key customizations:** Model selection, hyperparameters, evaluation metrics, horizon
- **Validation focus:** Model trains, metrics compute

### File Locations

```
.github/agents/time-series-forecaster.md

.github/prompts/
├── tsf-01-intake-discovery.prompt.md
├── tsf-02-scenario-interpretation.prompt.md
├── tsf-03-customization-planning.prompt.md
├── tsf-04-notebook-generation.prompt.md
└── tsf-05-finalization.prompt.md
```

### Invocation

The user (or orchestrating system) invokes prompts sequentially. Each prompt picks up context from the previous phase and produces outputs for the next. The agent file (`time-series-forecaster.md`) provides the overarching persona, tools, and boundaries that apply across all prompts.

---

## 9. Agent Implementation Guide

This section describes how to implement the agent using the AGENTS.md open format and the project's agent/prompt conventions.

### About AGENTS.md

[AGENTS.md](https://agents.md) is an open-source format for guiding AI coding agents, used by over 20,000 open-source projects. Think of it as a README for agents — a dedicated, predictable place to provide context and instructions.

**Key characteristics:**
- Standard Markdown format (no proprietary syntax)
- No required fields — use any headings that make sense
- Works across many AI agents (GitHub Copilot, Cursor, Aider, etc.)
- Can be nested in subfolders for monorepo/multi-project setups

### Project Conventions

This project uses a two-part structure for agents:

| Component | Location | Purpose |
|-----------|----------|----------|
| **Agent file** | `.github/agents/<agent-name>.md` | Defines persona, tools, boundaries, and standards |
| **Prompt files** | `.github/prompts/<prefix>-NN-<phase>.prompt.md` | Codifies workflow phases with checkpoints |

### Agent File Template

Use the template at `.github/agents/agent_template.md` as a starting point:

```markdown
---
name: your-agent-name
description: One-sentence description of what this agent does
---

You are an expert [role] for this project.

## Persona
- You specialize in [capabilities]
- You understand [domain knowledge]
- Your output: [deliverables]

## Project Knowledge
- **Tech Stack:** [technologies]
- **File Structure:** [key paths]

## Tools You Can Use
- [Tool descriptions and usage]

## Standards
- [Naming conventions]
- [Code style]

## Boundaries
- ✅ **Always:** [required behaviors]
- ⚠️ **Ask first:** [requires approval]
- 🚫 **Never:** [prohibited actions]
```

### Agent File Example

Reference the existing migration agent at `.github/agents/fabric_ds_migration_agent.md`:

```markdown
---
name: fabric_ds_agent
description: Expert data scientist for migrating Python notebooks to Microsoft Fabric
---

You are an expert data scientist specializing in migrating Python/Pandas 
notebooks to Microsoft Fabric using Spark and Lakehouse tables.

## Persona
- Senior data scientist with expertise in Python data science and Microsoft Fabric
- Can migrate any Python notebook to Fabric-compatible code
- Validates code interactively using Spark/Livy sessions

## Capabilities

### Fabric MCP Tools
- `list_workspaces()` - List all accessible workspaces
- `livy_create_session(...)` - Create Spark session
- `livy_run_statement(...)` - Execute code
...

## Boundaries
### ✅ Always Do
- Validate code cells via Livy before appending to target
- Close Livy sessions when done
...

### 🚫 Never Do
- Hardcode file paths from source notebooks
- Leave broken/unvalidated code in target
...
```

### Prompt File Template

Each prompt file follows this structure:

```markdown
# [Phase Name]

[Brief description of what this phase accomplishes]

## Prerequisites
- [What must be complete before this phase]

## Inputs
- [What the agent needs to proceed]

## Notebook References (if applicable)
| Notebook | Path | Purpose |
|----------|------|---------|
| ... | ... | ... |

## Steps
1. [Detailed step instructions]
2. [Detailed step instructions]
...

## Checkpoints
- **Checkpoint X.Y**: [What to present, what approval is needed]

## Error Handling
- [Phase-specific error guidance]

## Outputs
- [What this phase produces for the next phase]

## Transition
- [How to hand off to the next phase]
```

### Prompt File Example

Reference the existing migration prompt at `.github/prompts/1-migrate-notebook.prompt.md`:

```markdown
# Notebook Migration Workflow

Migrate a Python/Pandas notebook to Microsoft Fabric.

## Phase 0: Get Source Notebook

If source notebook path is not provided, ask the user:

🚀 **Fabric Notebook Migration Assistant**

Please provide:
1. **Source notebook path**: Which notebook would you like to migrate?
2. **Target notebook path**: Where should I save the migrated notebook?

Wait for the user to provide the source notebook path before proceeding.

## Phase 1: Analyze Notebook & Gather Requirements

After receiving the source notebook path:

1. **Read the entire source notebook** to understand:
   - What data sources are used
   - What configuration parameters are referenced
   - What custom modules/libraries are imported
   ...

2. **Ask the user for required inputs** based on your analysis
...

## Phase 2: Setup Livy Session

1. Use `list_workspaces` to get workspace ID
2. Use `list_items` with `item_type="Lakehouse"` to get lakehouse ID
3. Use `livy_create_session` to create a PySpark session
4. Wait for session state to be `idle` before proceeding

## Phase 3: Cell-by-Cell Migration
...
```

### Best Practices for Agent/Prompt Design

**Agent Files:**
1. Keep persona focused — one clear role per agent
2. List tools with brief usage examples
3. Be explicit about boundaries (Always/Ask First/Never)
4. Reference project-specific paths and conventions

**Prompt Files:**
1. One prompt per workflow phase (single responsibility)
2. Explicit checkpoints with clear approval criteria
3. Reference specific files/notebooks the phase operates on
4. Include error handling guidance per phase
5. Define clear handoff to the next phase

**Checkpoint Design:**
1. Place checkpoints after analysis, before action
2. Present findings in structured format (tables, lists)
3. Offer clear options (approve / modify / reject)
4. For high-risk changes, require explicit "yes" rather than silence

### File Organization for This Agent

```
.github/
├── agents/
│   ├── agent_template.md                    # Generic template
│   ├── fabric_ds_migration_agent.md         # Existing migration agent
│   └── time-series-forecaster.md            # NEW: This agent
│
└── prompts/
    ├── 1-migrate-notebook.prompt.md              # Existing migration prompt
    ├── tsf-01-intake-discovery.prompt.md         # TSF Phase 1
    ├── tsf-02-scenario-interpretation.prompt.md  # TSF Phase 2
    ├── tsf-03-customization-planning.prompt.md   # TSF Phase 3
    ├── tsf-04-notebook-generation.prompt.md      # TSF Phase 4
    └── tsf-05-finalization.prompt.md             # TSF Phase 5
```

---

## Appendix: Related Documentation

- [Pipeline Overview](migration/00_Pipeline_Overview.md) — Detailed pipeline documentation
- [Data Preparation Migration](migration/01_DataPreparation_Migration.md) — Notebook 01 details
- [Profiling Migration](migration/02_ProfilingIntermittent_Migration.md) — Notebook 02 details
- [Clustering Migration](migration/03_Clustering_Migration.md) — Notebook 03 details
- [Feature Engineering Migration](migration/04_FeatureEngineering_Migration.md) — Notebook 04 details
- [Train/Test/Tune Migration](migration/05_TrainTestSelectTune_Migration.md) — Notebook 05 details
