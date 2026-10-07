# Aggregate anchor report — `<scenario>` · level `<product_family>` · served `<FYyy-Qn>`

## Backtest of the quarter total (`<5>` leak-free quarters) — mean APE %
| output | family A | family B | … |
|---|---|---|---|
| Q-LGBM ratio q70 | | | |
| Q-LGBM ratio mean | | | |
| Q-LGBM raw q75 | | | |
| Q-LGBM raw q50 | | | |
| TOTAL snaive | | | |

Mean **signed** error of the `q50` sums: `<negative for the lumpy families>` → anchor to q75 / mean, never q50.

## Views chosen
| view | output | why |
|---|---|---|
| upside | `Q-LGBM raw q75` | right in surge quarters, over-forecasts flat ones |
| plateau (technical) | `Q-LGBM ratio mean` | right in flat quarters, misses surges |

## Range on the validation folds (M)
| family | quarter | actual | blend | blend APE | upside | upside APE | factor | plateau | plateau APE |
|---|---|---|---|---|---|---|---|---|---|

Mean APE over folds: blend `<x>` · upside `<y>` · plateau `<z>` — portfolio: `<…>`

## Served quarter (M)
| family | booked | blend | upside | plateau | range lo .. hi | upside output | business estimate | verdict |
|---|---|---|---|---|---|---|---|---|

## Decisions
- Families reconciled: `<list>` (anchor has a track record on the folds); not reconciled: `<list>`.
- Published: **blend .. upside**; plateau stays a technical column.
