# Forecast waterfall — `<group>` · `<served quarter>`

## What moved the published number (model drivers, exact SHAP of the blend)
| step | measure | value (M) | running total (M) |
|---|---|---|---|
| baseline | absolute | | |
| recent level (lag 2-3) | relative | | |
| last year (lag 12) | relative | | |
| seasonality / calendar | relative | | |
| not modelled by SHAP | relative | | |
| forecast months | total | | |
| booked actual | relative | | |
| `<quarter>` published (full quarter) | total | | |

## Business scenario (what-if, outside the model)
| scenario | price surge | qty surge | factor | Δ from price (M) | Δ from qty (M) | scenario total (M) |
|---|---|---|---|---|---|---|

## Factor definitions
- **baseline** — expected value before any recent or seasonal signal (average training level + series identity)
- **recent level (lag 2-3)** — run-rate / momentum effect of the last observed months
- **last year (lag 12)** — year-over-year anchor
- **seasonality / calendar** — fiscal position, quarter-end / year-end, days in month
- **not modelled by SHAP** — seasonal-naive series + rule lifts that the quantile models do not produce
- **booked actual** — realised months at their actual value
- **what-if surge** — business-stated assumption; revenue = price × quantity; applied to forecast months only

## Checks
- Every `total` equals the sum of the bars before it: `<ok>`
- Scenario total = published forecast months × factor + booked: `<ok>`
