# Quantile blend model card — `<scenario>` · data through `<DATA_MAX>` · served `<FYyy-Qn>`

## Folds (anchored to the last data month)
| fold | quarter | origin | months | scored rows (strict) |
|---|---|---|---|---|
| fold1 | | | | |
| final | | | | served; booked months carry actuals |

## Per-cluster recipe
| cluster | n series | params | blend | rules | committed method |
|---|---|---|---|---|---|
| strategic | 1 | single-series (num_leaves 3, reg on) | `0.20*q70 + 0.80*q90` | up > 10 % → q90; qty ≤ −50 % → q20 | blend+rules |
| smooth | | pooled | | — | blend |
| erratic | | pooled | | — | blend |
| others | | — | — | — | seasonal naive |

## Quantile crossing (first fold, as served)
| cluster | params | crossing rate raw | after rearrangement | q90/q50 median |
|---|---|---|---|---|

## Blend tuning (strict frames, revenue-focus series, bias cap ±15 %)
| cluster | strict WMAPE | bias | readable WMAPE | unconstrained WMAPE / bias | snaive | oracle |
|---|---|---|---|---|---|---|

## Commit gate (WMAPE %)
| cluster | snaive | blend readable | blend strict | rules readable | rules strict | fired share | committed |
|---|---|---|---|---|---|---|---|

## Served quarter
| cluster | series | committed (M) | seasonal naive (M) | method |
|---|---|---|---|---|

## Decisions / caveats
- Number quoted: **strict**.
- Rules kept for: `<clusters>`; off for `<clusters>` (readable < strict ⇒ firing on extrapolated trends).
- Headroom vs oracle: `<pts>` → `<tune more / change model family / aggregate anchor>`.
