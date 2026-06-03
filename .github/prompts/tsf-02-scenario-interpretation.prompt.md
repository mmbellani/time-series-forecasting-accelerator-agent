# Phase 2: Scenario Interpretation

Interpret the user's forecasting scenario and infer customization parameters based on data profile and domain knowledge.

## Prerequisites

- Phase 1 completed: Data profile confirmed by user
- **Completion report** from Phase 1 (user provides path)

## Phase Start — Read Completion Report

At the start of this phase:
1. Read the completion report from the path provided by user
2. Extract Phase 1 data: workspace info, table name, column mapping, data profile, scenario description
3. Use this context for scenario interpretation

### Context from Phase 1 (via completion report):
  - workspace_name, workspace_id, lakehouse_name, lakehouse_id
  - table_name, column_mapping (date, target, IDs, regressors)
  - data_profile (row_count, date_range, series_count, granularity, hierarchy)
  - scenario_description (user's original request)

## Interpretation Framework

Analyze the scenario description and data profile to infer parameters across these dimensions:

### 1. Time Granularity

| Signal | Inference |
|--------|-----------|
| Data gaps ~1 day | Daily granularity |
| Data gaps ~7 days | Weekly granularity |
| Data gaps ~30 days | Monthly granularity |
| User mentions "weekly forecast" | Weekly aggregation needed |
| User mentions "daily" | Daily granularity |

**Decision:** Match data granularity or aggregate if user requests coarser level.

### 2. Forecast Horizon

| Signal | Inference |
|--------|-----------|
| User says "next 4 weeks" | horizon = 4 (weekly) |
| User says "12 months ahead" | horizon = 12 (monthly) |
| User says "next quarter" | horizon = 13 weeks or 3 months |
| No explicit mention | Default based on granularity: daily=30, weekly=8, monthly=6 |

**Decision:** Extract explicit horizon or apply sensible default.

### 3. Series Structure

| Signal | Inference |
|--------|-----------|
| series_count = 1 | Single series (simplest case) |
| series_count < 50 | Multi-series, individual models feasible |
| series_count > 50 | Multi-series, clustering beneficial |
| Multiple ID columns with nesting | Hierarchical structure |
| User mentions "by store", "by product" | Grouped forecasting |

**Decision:** Determine if clustering notebook is needed; identify hierarchy levels.

### 4. Seasonality Patterns

| Signal | Inference |
|--------|-----------|
| Daily data, retail/sales domain | Weekly seasonality (7-day cycle) |
| Monthly data | Annual seasonality (12-month cycle) |
| User mentions "holiday effects" | Calendar features important |
| User mentions "quarterly patterns" | Quarterly seasonality |
| Financial/banking domain | Business day calendar needed |

**Decision:** Set lag windows and seasonal features accordingly.

### 5. Intermittency & Demand Patterns

| Signal | Inference |
|--------|-----------|
| Zero values > 30% | Intermittent demand likely |
| High CV² (coefficient of variation) | Erratic demand |
| User mentions "slow movers" | Intermittent handling critical |
| User mentions "sparse data" | Profiling notebook important |

**Decision:** Emphasize profiling; may need specialized models (Croston, etc.)

### 6. External Regressors

| Signal | Inference |
|--------|-----------|
| User mentions "promotions" | Promotion calendar as regressor |
| User mentions "holidays" | Holiday flags as features |
| User mentions "weather" | Weather data integration |
| User mentions "price" | Price elasticity features |
| Additional columns in data | Potential regressors |

**Decision:** Identify regressor columns; add to feature engineering.

### 7. Industry-Specific Considerations

| Industry | Considerations |
|----------|----------------|
| Retail | Stockouts, promotions, seasonality, markdown periods |
| CPG/FMCG | Trade promotions, distribution, new product launches |
| Manufacturing | Lead times, capacity constraints, demand sensing |
| Financial | Business day calendars, market closures, volatility |
| Healthcare | Appointment patterns, seasonal illness, capacity |
| Energy | Weather dependency, peak demand, regulatory factors |

**Decision:** Apply domain-specific preprocessing or feature logic.

### 8. Model Preferences

| Signal | Inference |
|--------|-----------|
| Default (no mention) | LightGBM (template default) |
| User mentions "ARIMA" | Add ARIMA to model selection |
| User mentions "Prophet" | Add Prophet to model selection |
| User mentions "ensemble" | Combine multiple models |
| User mentions "explainability" | Prefer interpretable models |
| User mentions "speed" | Prioritize fast training (LightGBM) |

**Decision:** Determine if model changes needed (high-risk if so).

### 9. Evaluation Criteria

| Signal | Inference |
|--------|-----------|
| Default | MAPE, RMSE, MAE (standard metrics) |
| User mentions "bias" | Add bias/ME metric |
| User mentions "accuracy by segment" | Segment-level evaluation |
| User mentions "forecast value added" | FVA analysis |
| Intermittent data | Use appropriate metrics (scaled MAE, hit rate) |

**Decision:** Configure evaluation metrics in Train/Tune notebook.

## Interpretation Process

1. **Parse scenario description** for explicit requirements
2. **Cross-reference with data profile** to validate inferences
3. **Apply domain knowledge** based on industry signals
4. **Identify gaps** where assumptions are needed
5. **Flag uncertainties** for user confirmation

## Checkpoint 2.1: Present Interpretation

Present your interpretation with rationale for each parameter:

```
🎯 **Scenario Interpretation**

Based on your description and data profile, here's my understanding:

**Scenario:** <derived scenario name from description>
> <user's original description>

---

### Inferred Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Time Granularity** | <value> | <why> |
| **Forecast Horizon** | <value> | <why> |
| **Series Structure** | <value> | <why> |
| **Seasonality** | <value> | <why> |
| **Intermittency** | <Low/Medium/High> | <why> |

### Column Assignments

| Role | Column | Notes |
|------|--------|-------|
| Date | <column> | <format/notes> |
| Target | <column> | <the value to forecast> |
| Series ID(s) | <columns> | <grouping level> |
| External Regressors | <columns or "None"> | <if applicable> |

### Pipeline Configuration

| Notebook | Configuration | Notes |
|----------|---------------|-------|
| 01 Data Prep | <key settings> | <any special handling> |
| 01b Exploratory Data Analysis | <key settings> | <data analysis handling> |
| 02 Profiling | <thresholds> | <intermittency handling> |
| 03 Clustering | <enabled/skip, params> | <cluster count, method> |
| 04 Features | <lags, windows, features> | <based on seasonality> |
| 05 Train/Tune | <models, metrics, horizon> | <optimization settings> |

### Risk Assessment

| Change Type | Count | Examples |
|-------------|-------|----------|
| Low Risk | <N> | <parameter substitutions> |
| Medium Risk | <N> | <structural changes> |
| High Risk | <N> | <algorithm/generative changes> |

---

**Questions for Clarification:**

<If any inferences are uncertain, list specific questions here>

1. <question about ambiguous requirement>
2. <question about data interpretation>

**Please review and confirm:**
- Are these interpretations correct?
- Any parameters you'd like to adjust?
- Ready to proceed to customization planning?

Reply with your answers, then type `continue` to record this checkpoint. Start Phase 3 in a new chat using `tsf-03-customization-planning.prompt.md` and the completion report path.
```

Checkpoint protocol (hard stop):
1. Log this checkpoint as **Pending** in `completion_report.md` (Checkpoint Log), including:
   - phase: `2`
   - notebook: (none)
   - cell index / step: `Checkpoint 2.1`
   - raw checkpoint text: the above checkpoint prompt
   - questions asked: the confirmation + clarification questions included above
   - answers: leave blank until user responds
2. Wait for the user to respond and type `continue`.
3. On `continue`, update the same checkpoint entry with the user’s answers and mark it completed, then STOP. The user will start Phase 3 in a new chat using `tsf-03-customization-planning.prompt.md` and the completion report path.

## Handling Ambiguity

If scenario description is vague or missing key details:

```
🤔 **Clarification Needed**

I need a bit more information to customize the pipeline correctly:

**Time Horizon:**
- How far ahead do you need to forecast? (e.g., 4 weeks, 3 months)

**Forecast Level:**
- Should forecasts be at <level A> or <level B>? 
  (e.g., by individual product or by category)

**Special Requirements:**
- Any external factors to include? (promotions, holidays, weather)
- Any specific models you prefer?

Please provide these details so I can proceed.
```

## Derived Scenario Name

Generate a short, descriptive name for the output folder:

**Format:** `<domain>_<granularity>_<key_feature>_forecast`

**Examples:**
- `retail_weekly_sku_forecast`
- `demand_daily_multistore_forecast`
- `sales_monthly_regional_forecast`
- `inventory_weekly_intermittent_forecast`

## Outputs for Next Phase

After user confirms interpretation, pass these to Phase 3:

- **scenario_name**: Derived folder name
- **parameters**:
  - time_granularity: daily | weekly | monthly
  - forecast_horizon: integer
  - series_structure: single | multi | hierarchical
  - hierarchy_levels: list of column groupings (if hierarchical)
  - seasonality: list of seasonal periods (7, 12, 52, etc.)
  - intermittency_level: low | medium | high
- **column_assignments**: Confirmed column roles
- **notebook_config**: Per-notebook configuration
  - data_prep: aggregation, date handling, null strategy
  - profiling: CV² threshold, ADI threshold
  - clustering: enabled, n_clusters, method
  - features: lags, rolling_windows, calendar_features, regressors
  - train_tune: models, metrics, horizon, optimization
- **risk_assessment**: Count by risk level
- **model_changes**: Any high-risk algorithm changes requested

## Phase Complete — STOP HERE

### Update Completion Report

Before stopping:
1. Read the existing completion report
2. Fill the **Phase 2: Scenario Interpretation** section with:
   - Derived scenario name
   - Inferred parameters table
   - Confirmed column assignments
   - Pipeline configuration preview
3. Mark Phase 2 as `[x]` complete in the Status section
4. Update the "Last Updated" timestamp
5. Save the updated completion report

### Present to User

```
✅ **Phase 2: Scenario Interpretation Complete**

I've documented the scenario interpretation in the completion report.

**STOPPING HERE.** To continue to Phase 3 (Customization Planning):
1. Start a new conversation or continue in a new message
2. Reference the phase 3 prompt: `tsf-03-customization-planning.prompt.md`
3. Provide the completion report path
