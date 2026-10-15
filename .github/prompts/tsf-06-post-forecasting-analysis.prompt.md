# Phase 6: Post-Forecasting Analysis

Run forecast explainability, error analysis, and hierarchical reconciliation against the
LightGBM models and forecast outputs produced by Notebook 06. Work with the data scientist at
explicit checkpoints so the analysis window, interpretation, hierarchy, and aggregation level
are confirmed before dependent analysis begins.

## Prerequisites

- Phase 5 completed, or Notebook 06 has otherwise run successfully
- **Completion report** from the prior phase (user provides path)
- Notebook 06 LightGBM model objects or persisted model artifacts are accessible
- `<scenario>_forecasts` exists with `unique_id`, date, actual, and prediction columns
- `<scenario>_features` exists for point-level explanations
- Hierarchy/static attributes can be joined to forecasts by `unique_id`

If any required artifact is unavailable, compute all feasible diagnostics, record the blocker in
the completion report, and stop at the relevant checkpoint. Do not retrain or retune models.

## Phase Start - Read Completion Report

At the start of this phase:

1. Read the completion report from the path provided by the user.
2. Restore `data_source`, `notebook_prefix`, `source_details`, `execution_environment`,
   `notebook_files`, `artifact_locations`, scenario, column mappings, forecast horizon,
   Notebook 06 model details, and execution status. Restore workspace/Lakehouse IDs only
   for Fabric. If the source contract is missing, confirm it rather than defaulting to Fabric.
3. Verify that Notebook 06 completed successfully and identify:
   - The selected LightGBM model and any per-cluster LightGBM models
   - The selected `y_hat_*` prediction column and all alternative prediction columns
   - The actual, date, series ID, cluster, static, and hierarchy candidate columns
   - The available forecast/actual date range
4. Add a `Phase 6: Post-Forecasting Analysis` section to the completion report if it does not
   already exist. Do not overwrite prior phase content.

Refer to Notebook 06 by its recorded source-prefixed filename:
`<notebook_prefix> 06 TrainTestSelectTune.ipynb`, with `notebook_prefix` equal to the
confirmed `Fabric`, `Databricks`, or `Local` data source. Resolve all notebook references
through `notebook_files`; any additional generated analysis notebook must use the same
prefix. Dataset names such as `<scenario>_forecasts` and `<scenario>_features` denote
the qualified tables or files recorded in `artifact_locations`, not necessarily Lakehouse
tables. Use the corresponding source readers and model locations; never switch sources
silently if an artifact is unavailable.

## Execution and Safety Rules

- Invoke the repository skills in this exact order:
  1. `forecast-explainability`
  2. `error-analysis`
  3. `hierarchical-reconciliation`
- Read each skill's `SKILL.md` before executing that step and follow its workflow and boundaries.
- Use the forecast and model artifacts produced by Notebook 06; do not train, tune, or modify a
  model.
- Treat feature importance, SHAP values, and error associations as evidence, not proof of
  causality.
- Prefer gain importance as the headline global-importance measure. Report split importance as
  secondary evidence.
- Use the error convention `error = actual - forecast` consistently.
- Do not modify source tables. Store reports and charts in `<output_folder>/post_forecasting/`.
- Validate generated analysis code in the confirmed execution environment before saving it. For
  Fabric, follow the standard Livy session rules: list sessions first, reuse an idle session, and
  create a session only when none is available. Never close the session.
- For Databricks, use the configured compute/connector; for Local, use the configured
  Python/Jupyter kernel and local files. Neither requires Fabric Livy or Lakehouse setup.
- At every checkpoint, compute feasible diagnostics first, present a concise summary, ask only
  the questions required to proceed, log a Pending checkpoint, and stop.

## Checkpoint Protocol (Hard Stop)

For every checkpoint in this prompt:

1. Log a new Pending entry in the completion report's `Checkpoint Log` with:
   - phase: `6`
   - notebook: `<notebook_prefix> 06 TrainTestSelectTune.ipynb` when model-specific, otherwise none
   - cell index / step: the checkpoint identifier
   - raw checkpoint text
   - questions asked
   - answers: blank
2. Stop immediately and wait for the data scientist to answer and type `continue`.
3. On `continue`, update that same entry with the answers, mark it Completed, and stop.
4. Resume in a new chat with this prompt and the same completion-report path, beginning after the
   completed checkpoint. Never repeat completed analysis unless the data scientist requests it.

---

## Step 1: Forecast Explainability

Use the `forecast-explainability` skill on the LightGBM model or per-cluster LightGBM models from
Notebook 06.

### 1.1 Verify Explainability Inputs

1. Locate the trained estimator/booster and exact feature names used by Notebook 06.
2. Confirm the mapping between models, clusters, transformations, and `y_hat_*` columns.
3. Verify that feature rows can be joined to forecast rows by series ID and date.
4. Identify static and external-regressor columns whose business meaning requires confirmation.
5. If in-memory models are unavailable after notebook execution, inspect persisted MLflow/model
   artifacts or rerun only the read-only explainability portion in the Notebook 06 execution
   context. Do not retrain.

### Checkpoint 6.1: Confirm Explainability Scope

Present the available models, forecast columns, clusters, feature families, and explainable date
range. Ask the data scientist:

1. Should explainability cover the selected best model only, all LightGBM variants, or selected
   clusters/models?
2. Which clusters, series, or forecast dates require point-level explanations?
3. What are the business meanings of ambiguous static or external-regressor features?

Log the checkpoint and stop. Do not compute or interpret final importances until the data
scientist confirms the scope and types `continue`.

### 1.2 Run Explainability Analysis

After Checkpoint 6.1 is completed in a prior chat:

1. Compute global feature importance using gain and split importance.
2. Group features into lag, rolling, calendar, static, categorical, and external-regressor
   families using actual feature names.
3. Compare importance across clusters when per-cluster models exist.
4. Compute SHAP or LightGBM `pred_contrib` explanations for the confirmed points.
5. Verify that additive contributions reconcile to each explained prediction within numerical
   tolerance.
6. Generate a concise business narrative that distinguishes global importance from point-level
   contribution and avoids causal claims.
7. Save tables, charts, and narrative to:
   - `<output_folder>/post_forecasting/forecast_explainability.md`
   - `<output_folder>/post_forecasting/feature_importance.csv`
   - `<output_folder>/post_forecasting/point_explanations.csv` when requested

### Checkpoint 6.2: Review Explainability Findings and Select Error Window

Present the leading feature families, cluster differences, point-level drivers, limitations, and
the available actual-versus-forecast date range. Then ask the data scientist:

1. Which time frame should be used to compute errors? Offer concrete choices based on available
   dates, such as:
   - A) Full holdout/test period
   - B) Most recent complete forecast horizon
   - C) A specific start and end date
   - D) Multiple named windows for comparison
2. Should error analysis cover the selected best prediction only or compare all `y_hat_*`
   variants?
3. Which calendar decompositions and business segments matter most?

The error window must contain observed actuals and predictions. Show row counts, series coverage,
missing-actual counts, and zero/near-zero actual prevalence for each proposed window before asking
for confirmation. Log the checkpoint and stop. Do not compute final error metrics until the data
scientist confirms the time frame and types `continue`.

---

## Step 2: Error Analysis

After Checkpoint 6.2 is completed in a prior chat, use the `error-analysis` skill with the exact
time frame and model scope selected by the data scientist.

### 2.1 Compute and Diagnose Errors

1. Filter to the confirmed date window before calculating metrics.
2. Join actuals and predictions by series ID and date; report dropped or unmatched rows.
3. Compute MAE, MAPE, ME, RMSE, WMAPE, and sMAPE for the selected model(s).
4. Compare model variants when requested.
5. Decompose errors by the confirmed calendar dimensions and relevant business segments.
6. Generate error-distribution plots and identify worst buckets, series, and dates.
7. Explicitly flag MAPE/sMAPE instability when actuals are zero or near zero; make MAE/WMAPE the
   headline metrics when appropriate.

### 2.2 Incorporate Forecast Explainability

When explainability findings are available:

1. Select representative high-error points from the worst buckets.
2. Retrieve their existing SHAP/`pred_contrib` explanations, or compute them using the same
   validated explainability path.
3. Compare their feature contributions with the global and cluster-level importance findings.
4. State whether evidence suggests stale lags, unusual rolling behavior, calendar effects,
   external regressors, or cluster-specific behavior, while avoiding unsupported causal claims.
5. Clearly separate observed error patterns from model-driver interpretations.

Save results to:

- `<output_folder>/post_forecasting/error_analysis.md`
- `<output_folder>/post_forecasting/error_metrics.csv`
- `<output_folder>/post_forecasting/error_by_calendar.csv`
- `<output_folder>/post_forecasting/error_by_segment.csv` when applicable

### Checkpoint 6.3: Review Error Findings

Present the confirmed analysis period, metric summary, bias direction, worst calendar/segment
buckets, model comparison, and explainability-informed interpretation. Ask the data scientist:

1. Are the selected time frame and metric priorities correct for the business decision?
2. Should any additional period, segment, model, or high-error point be analyzed before roll-up?
3. Which findings are accepted for use in hierarchical reconciliation, and which require caveats?

Log the checkpoint and stop. Do not begin hierarchical reconciliation until the data scientist
accepts or adjusts the findings and types `continue`.

---

## Step 3: Hierarchical Reconciliation

After Checkpoint 6.3 is completed in a prior chat, use the `hierarchical-reconciliation` skill.
Always ask the data scientist to define the hierarchy; never infer and proceed without explicit
confirmation.

### 3.1 Discover Hierarchy Candidates

1. Inspect static attributes associated with each `unique_id` and list plausible hierarchy
   columns.
2. Compute feasible node counts, null rates, uniqueness, and parent-child nesting diagnostics.
3. Identify whether each child maps to exactly one parent at every proposed level.
4. Identify available aggregation dates within the error-analysis time frame.

### Checkpoint 6.4: Define and Confirm the Hierarchy

Present candidate hierarchy columns and diagnostics. Ask the data scientist:

1. Which columns define the hierarchy, ordered from top/coarsest to bottom/finest?
2. At which level should forecasts be aggregated and reconciled, or should the grand `Total` be
   used?
3. Should reconciliation use the same time frame and prediction column approved for error
   analysis? If not, request the exact alternatives.

After receiving answers in a later `continue` turn, run `describe_hierarchy()` and
`validate_hierarchy()` and present node counts, invalid nesting, missing mappings, and proposed
handling. If validation changes or contradicts the requested hierarchy, create another Pending
checkpoint and obtain confirmation before continuing. Log Checkpoint 6.4 and stop.

### 3.2 Run Bottom-Up Reconciliation and Diagnostics

Only after the hierarchy and target aggregation level are explicitly confirmed:

1. Assemble base actuals and forecasts with the confirmed hierarchy columns.
2. Aggregate bottom-up to every hierarchy level and the selected target level.
3. Verify coherence: children must sum to parents within numerical tolerance.
4. Chart actual versus forecast at the target level.
5. Compute level contributions and identify dominant nodes.
6. Compute error by level, error contribution, and error cancellation/reinforcement.
7. Use accepted explainability findings for dominant nodes and accepted error findings for driver
   nodes. Do not claim aggregate causes without both forms of supporting evidence.
8. Use `coherence_gap()` only if a separately modeled direct aggregate forecast exists.
9. Explain every chart and state whether aggregation improves reliability through cancellation or
   preserves systematic bias through reinforcement.

Save results to:

- `<output_folder>/post_forecasting/hierarchical_reconciliation.md`
- `<output_folder>/post_forecasting/reconciled_forecasts.csv`
- `<output_folder>/post_forecasting/error_by_level.csv`
- `<output_folder>/post_forecasting/node_contributions.csv`

### Checkpoint 6.5: Review Reconciliation Findings

Present the validated hierarchy, target level, coherence result, dominant contributors, aggregate
accuracy, cancellation/reinforcement behavior, and linked explainability/error evidence. Ask the
data scientist:

1. Does the hierarchy and aggregation level reflect the business reporting structure?
2. Are the contribution and error-propagation interpretations acceptable?
3. Should any hierarchy level, period, or dominant node receive additional analysis?

Log the checkpoint and stop. Do not finalize Phase 6 until the data scientist approves the
findings and types `continue`.

---

## Step 4: Finalize Phase 6

After Checkpoint 6.5 is completed in a prior chat:

1. Create `<output_folder>/post_forecasting/post_forecasting_analysis.md` summarizing:
   - Model drivers and point-level explanations
   - The data-scientist-approved error time frame and model scope
   - Accuracy, bias, worst periods/segments, and model comparison
   - The confirmed hierarchy and aggregation level
   - Aggregate composition, coherence, and error propagation
   - Limitations, caveats, and recommended follow-up actions
2. Update the completion report:
   - Add Phase 6 to the Status section and mark it complete
   - Set Last Updated to the current date with `(Phase 6)`
   - Reference all Phase 6 checkpoint IDs
   - Record the selected model, prediction column, error window, metrics, hierarchy, target level,
     validation results, output artifacts, errors, and resolutions
3. Verify that all analysis artifacts exist and contain no credentials or secrets.
4. Present a concise final summary and the completion-report path.
5. Stop. Do not begin model remediation, retraining, or another phase automatically.

## Required Phase 6 Completion Report Section

Use this structure when adding Phase 6 to `completion_report.md`:

```markdown
## Phase 6: Post-Forecasting Analysis

### Checkpoints
- CP-#### - Explainability scope
- CP-#### - Explainability findings and error window
- CP-#### - Error findings
- CP-#### - Hierarchy definition and validation
- CP-#### - Reconciliation findings

### Forecast Explainability
| Attribute | Value |
|-----------|-------|
| Model(s) | |
| Prediction Column(s) | |
| Clusters/Series | |
| Leading Feature Families | |
| Point Explanations | |

### Error Analysis
| Attribute | Value |
|-----------|-------|
| Start Date | |
| End Date | |
| Series Coverage | |
| Primary Metric | |
| MAE | |
| MAPE | |
| ME | |
| RMSE | |
| WMAPE | |
| sMAPE | |
| Worst Buckets | |

### Hierarchical Reconciliation
| Attribute | Value |
|-----------|-------|
| Hierarchy Levels | |
| Target Level | |
| Hierarchy Valid | |
| Coherent | |
| Dominant Nodes | |
| Error Cancellation/Reinforcement | |

### Artifacts
| Artifact | Status |
|----------|--------|
| post_forecasting/forecast_explainability.md | |
| post_forecasting/error_analysis.md | |
| post_forecasting/hierarchical_reconciliation.md | |
| post_forecasting/post_forecasting_analysis.md | |

### Limitations and Recommendations
<!-- Record caveats and approved next actions. -->
```

## Error Handling

- **Model artifact unavailable:** Inspect persisted model/MLflow artifacts. If still unavailable,
  report which explainability analyses cannot run and stop at Checkpoint 6.1.
- **Feature mismatch:** Compare the model's feature names with Notebook 05/06 inputs. Do not
  reorder or impute silently; report and resolve the mismatch before calculating SHAP values.
- **No actuals in selected period:** Show the available actual date range and return to Checkpoint
  6.2 for a new time-frame decision.
- **Sparse or zero actuals:** Report affected row share and prioritize MAE/WMAPE over MAPE.
- **Invalid hierarchy:** Show offending child-parent mappings and ask the data scientist to revise
  levels or approve an explicit mapping rule. Never repair hierarchy mappings silently.
- **Non-coherent roll-up:** Stop, report the tolerance and offending nodes/dates, and diagnose the
  aggregation keys before interpretation.
- **Validation failure:** Follow the standard three-attempt retry protocol, record each attempted
  fix, and escalate with concrete options after the third failure.

## Outputs

All deliverables are written under `<output_folder>/post_forecasting/`:

| Artifact | Required | Description |
|----------|----------|-------------|
| `forecast_explainability.md` | Yes | Global, cluster, and point-level model drivers |
| `feature_importance.csv` | Yes | Gain/split importance by feature and family |
| `point_explanations.csv` | When requested | SHAP/`pred_contrib` details |
| `error_analysis.md` | Yes | Approved-window accuracy and error decomposition |
| `error_metrics.csv` | Yes | Overall and model-comparison metrics |
| `error_by_calendar.csv` | Yes | Calendar error decomposition |
| `error_by_segment.csv` | When applicable | Segment-level error metrics |
| `hierarchical_reconciliation.md` | Yes | Roll-up, composition, and error propagation |
| `reconciled_forecasts.csv` | Yes | Bottom-up aggregate actuals and forecasts |
| `error_by_level.csv` | Yes | Accuracy and bias by hierarchy level |
| `node_contributions.csv` | Yes | Forecast and error contribution by node |
| `post_forecasting_analysis.md` | Yes | Integrated final report |

## Phase Complete

```text
Phase 6: Post-Forecasting Analysis ......... Complete
         Forecast Explainability ........... Complete
         Error Analysis .................... Complete
         Hierarchical Reconciliation ....... Complete

Output: <output_folder>/post_forecasting/
Completion report: <completion_report_path>
```