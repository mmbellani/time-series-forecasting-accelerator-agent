# Hierarchical Reconciliation - supermarket_net_sales_forecast



_Phase 6, Step 3.2. Read-only bottom-up aggregation of the approved Notebook 06 walk-forward predictions; no model or source table was modified._



## Approved scope



| Attribute | Value |

|---|---|

| Hierarchy | `STORE_ARCHETYPE -> STORE_LOCATION_ID` |

| Target level | `STORE_ARCHETYPE` |

| Prediction | `y_hat_identity` |

| Window | 2025-01-27 to 2025-03-17 |

| Coverage | 350 rows, 50 stores, 7 available dates |

| Missing date treatment | 2025-03-03 remains absent; no imputation |

| Error convention | actual - forecast; positive = under-forecast |



## Hierarchy validation



Hierarchy has **2 level(s)**: `STORE_ARCHETYPE` → `STORE_LOCATION_ID` (top → bottom).
Reconciling **bottom-up** to the **STORE_ARCHETYPE** level.

Level shape:
- `Total`: 1 node(s), ~1.0 children per parent.
- `STORE_ARCHETYPE`: 3 node(s), ~3.0 children per parent.
- `STORE_LOCATION_ID`: 50 node(s), ~16.7 children per parent.



Validation passed: every one of the 50 stores maps to exactly one non-null archetype. The hierarchy contains 3 archetypes (`large`, `medium`, `small`) and 50 base stores.



## Forecast composition



Aggregate forecast at **STORE_ARCHETYPE** = **167,664,207 USD** across 3 node(s).
The top 3 node(s) make up **100%** of the aggregate; ~**3 node(s)** account for 80%.

Largest contributors to the aggregate forecast:
- **medium**: 94,468,409 USD (56.3%)
- **large**: 38,285,882 USD (22.8%)
- **small**: 34,909,916 USD (20.8%)

The completed explainability analysis shows that the global forecast is primarily lag-led (75.4% of gain, almost entirely `lag1`), with static store attributes and calendar position providing secondary signal. This evidence describes model behavior and does not establish business causation.



| Archetype | Forecast total | Forecast share | Signed error | Direction | Gross-error share |

|---|---:|---:|---:|---|---:|

| large | $38,285,882 | 22.8% | $577,781 | under-forecast | 18.2% |
| medium | $94,468,409 | 56.3% | $1,795,845 | under-forecast | 61.5% |
| small | $34,909,916 | 20.8% | $610,459 | under-forecast | 20.3% |



![Archetype aggregate fit](reconciliation_aggregate_fit.png)



![Forecast contribution by archetype](reconciliation_contributions.png)



The contribution ranking is arithmetic composition, not a causal explanation. Feature-weight evidence from the completed explainability step remains associative.



## Error propagation



Base-level accuracy: MAPE **6.7%**, WMAPE **6.1%**, ME **8,526 USD**.
Aggregate (Total) accuracy: MAPE **4.1%**, WMAPE **4.1%**, ME **426,298 USD** → the aggregate is **under-forecasting (actuals exceed forecasts)**.

**71% of gross base error cancels** at the STORE_ARCHETYPE level — base misses are largely noise that averages out, so the aggregate is more reliable than the base series.

Nodes driving the net error at **STORE_ARCHETYPE** (signed):
- **medium**: 1,795,845 USD (under-forecast), 61.5% of gross error.
- **small**: 610,459 USD (under-forecast), 20.3% of gross error.
- **large**: 577,781 USD (under-forecast), 18.2% of gross error.

The completed error analysis identifies 2025-03-17 as the worst observed date and confirms that all three archetypes retain under-forecast bias. Checkpoint CP-0017 approved `medium` as the dominant forecast contributor and aggregate error driver.



| Level | n | ME | MAE | RMSE | MAPE | WMAPE | Cancellation |

|---|---:|---:|---:|---:|---:|---:|---:|

| Total | 7 | $426,298 | $1,011,135 | $1,256,645 | 4.08% | 4.15% | 71.2% |
| STORE_ARCHETYPE | 21 | $142,099 | $345,275 | $496,067 | 3.99% | 4.25% | 71.2% |
| STORE_LOCATION_ID | 350 | $8,526 | $29,578 | $37,233 | 6.66% | 6.07% | 64.9% |



![Error by hierarchy level](reconciliation_error_by_level.png)



![Archetype error propagation](reconciliation_error_propagation.png)



## Coherence



Bottom-up reconciliation is coherent by construction. The maximum absolute difference between summed store forecasts/actuals and their archetype roll-up is **$0.000000**, within the $10^{-6}$ tolerance. No separately trained direct archetype model was supplied, so MinT/direct-model gap analysis is not applicable.



## Artifacts



| File | Description |

|---|---|

| `reconciled_forecasts.csv` | Actuals, forecasts, and errors by archetype/date |

| `error_by_level.csv` | Accuracy and cancellation from Total to archetype to store |

| `node_contributions.csv` | Archetype forecast composition and signed error contribution |

| `reconciliation_*.png` | Aggregate fit, composition, level error, and propagation charts |

