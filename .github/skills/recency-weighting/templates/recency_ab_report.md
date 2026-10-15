# Recency weighting A/B — `<scenario>` · data through `<DATA_MAX>`

## Setup
- Blends frozen to the committed recipe (notebook 09) · strict rows · folds `<list>`
- Schemes: uniform · hl6 · hl9 · hl12 · window18 · hl9_gated (ratio `<1.30>`, min history `<18>` months)

## Gate coverage
| origin | strategic | smooth | erratic |
|---|---|---|---|
| fold1 | | | |
| served | | | |

## WMAPE (%) per cluster × scheme
| scheme | strategic | smooth | erratic |
|---|---|---|---|
| uniform | | | |
| hl9 | | | |
| window18 | | | |
| hl9_gated | | | |

## Net bias (%) per cluster × scheme
| scheme | strategic | smooth | erratic |
|---|---|---|---|

## Per-series view
- share of focus series helped by hl9: `<x %>` · correlation(surge ratio, benefit): `<r>`
- `<attach scatter: benefit vs surge ratio, gated series highlighted>`

## Recommendation
| cluster | recommended scheme | uniform WMAPE | recommended WMAPE | gain pts | bias |
|---|---|---|---|---|---|

## Decision
- Wire `gated_halflife_weights(h=<9>)` into the engine for: `<clusters>`; keep uniform for: `<clusters>`.
- Re-run the A/B every quarter: the gate re-evaluates itself at each origin.
