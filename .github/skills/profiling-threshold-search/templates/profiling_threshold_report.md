# Profiling threshold review — `<scenario>`

## Setup
- Sizes from `<quantity>`, occurrences from `<orders>`, scored on `<y>` · horizon `<6>` · season `<12>`
- Routing: smooth→snaive, erratic→median12, intermittent→rate12, lumpy→rate24, constant→last, constant_zero→zero
- Guardrail: regular group ≥ `<40>` % of revenue and ≥ `<40>` series

## Result

| candidate | thres_cv2 | thres_adi | portfolio WMAPE % | regular revenue share | n regular | feasible |
|---|---|---|---|---|---|---|
| textbook | 0.49 | 1.32 | | | | |
| best feasible | | | | | | ✔ |
| unconstrained optimum | | | | | | |
| routing oracle (floor) | – | – | | – | – | – |

## Quadrant picture
`<attach the ADI × CV² scatter: chosen cut-offs vs textbook, marker size = revenue share>`

## Profile mix and simple-method floor

| profile_cluster | n series | revenue share | method | WMAPE % | median MASE | modelling route |
|---|---|---|---|---|---|---|
| strategic | | | | | | quantile models, own cluster |
| smooth | | | | | | quantile models |
| erratic | | | | | | quantile models (bias cap) |
| intermittent | | | | | | Croston family |
| lumpy | | | | | | Croston family / aggregate anchor |
| constant / constant_zero / possible_obsolete / new_expansion | | | | | | seasonal naive |

## Decisions
- Thresholds adopted: `<cv2 / adi>` · guardrail kept at `<x>` %.
- Open question for the business: `<which groups must be modelled as regular demand>`.
