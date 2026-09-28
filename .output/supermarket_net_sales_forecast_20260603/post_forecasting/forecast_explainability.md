# Forecast Explainability — supermarket_net_sales_forecast

_Phase 6, Step 1 (forecast-explainability). Generated from a read-only reproduction of
Notebook 06's selected model. No retraining or retuning was performed._

## Scope and configuration (as executed in the live Notebook 06)

| Attribute | Value |
|-----------|-------|
| Selected transform | `identity` (selection metric MAE) |
| Model family | LightGBM (`LGBMRegressor`, random_state=42) via MLForecast |
| Frequency | `W-MON` |
| Generated lags | `lag1`, `lag2` |
| Calendar features | `year`, `month`, `week` |
| Static features | 15 store/market/competitor attributes incl. `BASELINE_WEEKLY_SALES`, `STORE_ARCHETYPE`, `REGION`, `profile_cluster` (all `category` dtype) |
| Model scopes | global + 5 per-cluster (`0.0`, `1.0`, `2.0`, `3.0`, `erratic`) |
| Training window | 2024-04-25 to 2025-02-27 |
| Point-explanation date | 2025-03-17 (last fully-observed week) |

> **Important divergences from the completion report (Phase 4.6 / CP-0013).** The live notebook
> now uses **W-MON** (report said W-THU), the **identity** transform (report said std),
> a reduced **18-column** feature set of mostly static store/market attributes plus calendar and
> two short lags (no dynamic media/weather/economic regressors, no lag52), and clusters
> `0.0/1.0/2.0/3.0/erratic` with 19/11/15/3/2 stores (report said erratic=12 and different
> cluster sizes). `BASELINE_WEEKLY_SALES` is **included** as a feature (the report had excluded it
> as collinear). These should be confirmed with the data scientist.

## Global feature importance (gain = headline, split = secondary)

Gain % by feature family across scopes:

| Family | cluster_0.0 | cluster_1.0 | cluster_2.0 | cluster_3.0 | cluster_erratic | global |
|---|---|---|---|---|---|---|
| calendar | 36.0 | 34.4 | 38.9 | 22.2 | 72.5 | 6.0 |
| categorical | 1.6 | 0.1 | 1.1 | 0.0 | 0.0 | 1.4 |
| lag | 51.9 | 55.0 | 50.3 | 36.9 | 26.3 | 75.4 |
| static | 10.5 | 10.4 | 9.8 | 40.9 | 1.2 | 17.2 |

Top features — global model:

| Feature | Family | Gain % | Split % |
|---|---|---|---|
| lag1 | lag | 74.8 | 15.1 |
| STORE_SELLING_AREA_SQFT | static | 16.3 | 7.5 |
| week | calendar | 4.9 | 43.5 |
| profile_cluster | categorical | 1.1 | 0.6 |
| month | calendar | 0.8 | 9.8 |
| lag2 | lag | 0.6 | 10.6 |
| COMPETITOR_DISCOUNT_A_PRESENT | static | 0.4 | 1.2 |
| MARKET_SHARE_AREA_POSTAL | static | 0.3 | 1.4 |

**Read:** the global model is driven primarily by the **lag** family — almost entirely `lag1`
(recent-history autocorrelation) — with `STORE_SELLING_AREA_SQFT` the leading static driver and
`week` the leading calendar signal. Note `week` has the **highest split share** but low gain: it is
used in many splits for fine adjustments but contributes little accuracy on its own. Report gain as
the headline; split is a secondary "how often used" signal only.

## Per-cluster differences

- Clusters `0.0`, `1.0`, `2.0`: lag-led (~50-55% gain) with strong calendar (~34-39%) — typical
  seasonal grocery behaviour.
- Cluster `3.0` (3 stores): **static-led** (40.9% gain) — small-sample store-identity effects
  dominate; interpret cautiously.
- Cluster `erratic` (2 stores): **calendar-led** (72.5% gain), weak lag — treat as low-confidence
  given only 2 series.
- `profile_cluster` is constant within each per-cluster model, so it contributes ~0 there (it only
  carries signal in the global model).

## Point-level explanations (2025-03-17, all 50 stores)

Additive `pred_contrib` decomposition (contributions + base value = raw prediction; additivity
verified to 1e-6). Mean absolute contribution by family, global model:

| Family | Mean |contribution| ($) |
|---|---|
| lag | 40,987 |
| calendar | 21,796 |
| static | 5,982 |
| categorical | 2,743 |

**Read:** at the last observed week, recent-history **lag** terms move individual store predictions
most, followed by **calendar** (seasonal position) and then **static** store attributes. This
mirrors the global gain ranking, so the model's per-store behaviour is consistent with its overall
driver profile. Per-store and per-cluster details are in `point_explanations.csv`.

## Caveats and limitations

- **Association, not causation.** Per CP-0013, service, pricing, market-share, loyalty, media, and
  volume features are treated as associative operational signals. (Most are not even in the current
  feature set.) Importance/contribution values describe the model, not real-world causal levers.
- **`BASELINE_WEEKLY_SALES`** is a near-target sales proxy; its presence can inflate apparent
  accuracy and mask other drivers. Confirm whether it should remain a feature.
- **Small clusters** (`3.0`=3 stores, `erratic`=2 stores) yield low-confidence importances.
- **Selected transform is `identity`**; importances reflect the untransformed-target model.
- Point explanations use realized lags at 2025-03-17 because the OOS horizon (2025-03-24) has no
  observed feature row; the report's 2025-03-27 does not exist in this W-MON run.

## Artifacts

| File | Description |
|------|-------------|
| `feature_importance.csv` | Gain/split importance by feature and family, all scopes |
| `point_explanations.csv` | Per-store additive `pred_contrib` at 2025-03-17, all scopes |
| `forecast_explainability.md` | This report |
