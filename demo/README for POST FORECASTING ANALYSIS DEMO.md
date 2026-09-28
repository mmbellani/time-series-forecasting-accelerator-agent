# How to Run the Explainability Demo

This guide walks through the supermarket forecasting browser demo, from forecast context to feature explanations, error review, what-if scenarios, and the saved reconciliation report.

## 1. Prepare the Demo

1. Clone the repository and open its folder in VS Code:

   ```powershell
   git clone https://github.com/mmbellani/time-series-forecasting-agent.git
   cd time-series-forecasting-agent
   ```

2. Open [supermarket_forecasting_demo_app.html](supermarket_forecasting_demo_app.html) in a web browser, for example by double-clicking it in File Explorer.
3. Keep the four report preview HTML files beside the app in the `demo` folder. Their relative links work without a fixed port or machine-specific directory.
4. Allow popups for the demo when prompted. Reports open in new tabs or windows.

No Python environment, dependency installation, cloud connection, Copilot subscription, or notebook execution is required for this browser walkthrough. The data and application logic are embedded in the HTML, and the reports are saved previews.

**Demo boundary:** the post-forecasting panel is a scripted checkpoint flow, not a live AI agent. Answers are displayed, but they do not recompute reports or change the saved analysis. A submission containing `continue` advances one checkpoint. The what-if panel applies predefined arithmetic assumptions; it does not rerun LightGBM or estimate causal effects.

## 2. Establish the Forecast Context

1. On **Dashboard**, show the data window, selected model, training and validation windows, and headline metrics. The saved demo contains 50 stores and 103 weeks, with headline WMAPE of 6.07%.
2. Select a **Store ID** to inspect one store, then return to **All stores** before using the **Cluster** filter. The store selection takes precedence over the cluster selection.
3. Optionally open **Profiling** to show the thresholds, profile counts, elbow chart, and silhouette chart. Explain that the app displays four regular clusters plus an erratic segment.
4. Open **Forecast results**. Use **Cluster** to compare **Overall** with individual clusters. Point out the actual-versus-forecast chart and the displayed evaluation period.
5. Open **Error analysis and explainability** for the remainder of the walkthrough.

Presenter message: "First we establish what was forecast and how well it matched actual sales. Then we inspect what drove the model and where its errors are concentrated."

## 3. Explore Errors and the Feature Waterfall

1. Scroll to the error distribution chart. Start with **Error metric: RMSE** and **Error frequency: Monthly**.
2. Change the metric to **MAE**, then **WMAPE**, to contrast absolute error with volume-weighted percentage error.
3. Change the frequency to **Weekly** to inspect finer time buckets. **Yearly** provides a coarser summary.
4. Review **Error analysis snapshot** for headline metrics and the worst date, month, and segment.
5. Under **Feature contribution waterfall**, change **Forecast segment** from **Overall** to a cluster and inspect the chart.

Treat the app waterfall as an illustrative model-weight visualization, not a fresh per-prediction SHAP computation. Likewise, some app error views use demo-grade store allocations from aggregate forecasts; do not present every chart as direct per-store model output. The saved explainability report provides the documented model-based contribution evidence.

## 4. Start the Checkpoint Walkthrough

Return to **Post-forecasting analysis** and click **Run post-forecasting analysis**. This starts at **Checkpoint 6.3: Error Findings**.

The scripted findings include:

- Prediction column: `y_hat_identity`.
- Coverage: 350 rows across 50 stores and 7 observed dates.
- MAE: $29,578; WMAPE: 6.07%; mean error: +$8,526.
- Error convention: actual minus forecast, so positive mean error indicates under-forecasting.
- Worst date: 2025-03-17, with MAE of $47,741.
- The 2025-03-03 forecast date is absent; no values were imputed.

The following five submissions complete the guided flow. Type each response in the text area and click **Submit**. Return to the original app tab after reading each report.

### Submission 1: Review Error Findings

Enter:

```text
Approve the 2025-01-27 to 2025-03-17 period and MAE/WMAPE priorities. Keep 2025-03-03 absent without imputation. No additional analysis is requested for this saved-demo walkthrough. Carry the under-forecast bias and worst segments into the roll-up, with small-cluster and association-not-causation caveats. continue
```

Expected result: [the error analysis preview](error_analysis_preview.html) opens. Review the approved scope, headline accuracy, worst buckets, and explainability-informed high-error points. Return to the app.

### Submission 2: Show the Explainability Scope

Enter:

```text
continue
```

Expected result: **Checkpoint 6.1** appears in the app. It asks whether to explain global, per-cluster, both, or selected models; which stores and dates to inspect; and whether to treat operational features as associative signals. This submission does not open a report.

The checkpoint text includes historical configuration details, including a March 6-27 explanation window, model availability notes, and a Fabric HTTP 404. These are scripted messages, not checks of your current environment. The saved report documents the actual scope used for its analysis.

### Submission 3: Open Forecast Explainability

Enter:

```text
C: both global and per-cluster models. For the saved report, review all 50 stores on 2025-03-17. Treat service, pricing, market-share, loyalty, media, and volume signals as associative, not causal. continue
```

Expected result: [the forecast explainability preview](forecast_explainability_preview.html) opens.

Walk through the report in this order:

1. **Scope and configuration:** LightGBM via MLForecast, `identity` transform, `W-MON` frequency, global plus five per-cluster models. The point-explanation date is 2025-03-17.
2. **Global feature importance:** lag features account for 75.4% of gain, static attributes 17.2%, calendar features 6.0%, and categorical features 1.4%. `lag1` alone accounts for 74.8%.
3. **Gain versus split:** gain is the headline importance measure. A feature such as `week` can be used in many splits without contributing the most gain. Gain percentages are not signed dollar contributions to a forecast.
4. **Per-cluster differences:** clusters 0.0, 1.0, and 2.0 are lag-led; cluster 3.0 is static-led; the erratic cluster is calendar-led. Emphasize the small samples in cluster 3.0 and erratic.
5. **Point-level explanations:** the report describes LightGBM `pred_contrib` decompositions whose base value plus contributions reproduce the raw prediction, with additivity verified to `1e-6`. This is distinct from global importance and from the app's illustrative waterfall.
6. **Limitations:** importance explains model behavior, not business causality. `BASELINE_WEEKLY_SALES` is a near-target proxy that can make apparent accuracy optimistic. These point explanations use realized lags at an observed date, not a newly explained future forecast.

Presenter message: "Recent sales dominate the global model, but different segments rely on different signals. Local additive contributions explain a specific model prediction; global gain tells us which features the model relies on overall. Neither proves causality."

### Submission 4: Show Reconciliation Choices

Return to the app and enter:

```text
continue
```

Expected result: **Checkpoint 6.4** asks for the hierarchy, target aggregation level, prediction column, and missing-date treatment. This submission does not open a report.

### Submission 5: Open the Saved Reconciliation

Although the checkpoint recommends option A (region), the saved report uses option B (store archetype). To keep the narrative aligned with the saved output, enter:

```text
B: STORE_ARCHETYPE -> STORE_LOCATION_ID. Aggregate to STORE_ARCHETYPE. Confirm y_hat_identity over 2025-01-27 to 2025-03-17, with no imputation for 2025-03-03. continue
```

Expected result: [the hierarchical reconciliation preview](hierarchical_reconciliation_preview.html) opens.

Review the bottom-up roll-up from 50 stores into three archetypes. Medium stores contribute 56.3% of the saved aggregate forecast. The report shows approximately 71% gross-error cancellation at the archetype level while under-forecast bias remains. Explain that arithmetic coherence does not eliminate bias or prove model accuracy.

Selecting another hierarchy in the text does not regenerate this report; it always opens the saved archetype analysis.

## 5. Run the What-If Demonstration

This panel is independent of the checkpoint walkthrough and can be shown before or after it.

1. Return to **Error analysis and explainability**.
2. Under **Feature contribution waterfall**, set **Forecast segment** to **Overall** or the cluster you want to demonstrate. This is the segment used by the what-if panel.
3. In **What-if scenario**, select **Promotion uplift**, leave the percentage input at `10`, and click **Run what-if scenario**.
4. Show the baseline, adjusted forecast, dollar change, and separate scenario-adjustment step. This scenario multiplies the segment baseline by 1.10.
5. Select **Supply constraint** with input `10` and run it again to demonstrate a 10% reduction.
6. Optionally demonstrate **Price change** or **Calendar event spike** using the table below.

| Scenario | Implemented assumption | Result for input `10` |
| --- | --- | --- |
| Promotion uplift | Apply the signed input percentage | +10% |
| Supply constraint | Subtract the absolute input percentage | -10% |
| Price change | Apply 35% of the signed input percentage | +3.5% |
| Calendar event spike | Add 60% of the absolute input percentage | +6% |

Use inputs between -50 and 50, as indicated by the control. Each run starts from the baseline; scenarios do not compound. After choosing another forecast segment, click **Run what-if scenario** again to update the scenario output for that segment.

Presenter message: "This is a sensitivity illustration based on an explicit assumption. It is not a model rerun, a causal estimate of promotion or price response, or a new SHAP explanation."

## 6. Finish With the Consolidated Report

Click **Complete post forecasting analysis** to open [the consolidated post-forecasting analysis preview](post_forecasting_analysis_preview.html). This button is available at any time; it opens an existing report rather than executing or completing a live pipeline.

Close with three questions: What drives the model? Where is it wrong? How do those errors behave when forecasts are aggregated?

## Reset and Troubleshooting

- **Restart checkpoints:** click **Run post-forecasting analysis** again. Reload the page for a full reset of filters, checkpoint responses, and what-if state.
- **Report did not open:** allow popups, then restart the checkpoint walkthrough. The scripted state can advance even if the browser blocks a report. Alternatively, open the report links in this guide.
- **Nothing advances:** include `continue` in the response and click **Submit**. Answers without that word are recorded but do not advance. Each submission advances only one step.
- **Broken report link:** ensure all five HTML files remain together in the `demo` folder. Open the cloned files in a browser, not GitHub's source-code view.
- **Different dates or numbers:** the app labels its validation window as 2025-01-06 to 2025-03-17, while the saved error/reconciliation reports cover seven observed weeks from 2025-01-27 to 2025-03-17. The explainability report also records configuration differences from earlier run notes. State the scope of the view you are presenting rather than treating all views as one identical evaluation.
- **Old local paths or missing figures inside reports:** saved report headers retain original generation paths as provenance; they are not required for opening the HTML. Some report figures appear as literal Markdown references rather than rendered charts. Do not assume the original source artifacts are included in the clone.

## Running New Analysis Instead of the Saved Demo

For a live pipeline run, follow [the local setup guide](mlads/README%20for%20DEMO.md). Actual model explainability requires compatible trained model objects and feature rows; the browser demo does not provide those objects or invoke Copilot skills. See [the forecast-explainability skill](../.github/skills/forecast-explainability/SKILL.md) for the read-only importance and prediction-explanation workflow.
