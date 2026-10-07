# Scaled accuracy report — `<scenario>` · data through `<DATA_MAX>`

## Validation setup
- Folds: `<fold list with quarters and origins>` · mode: **strict (as served)** / readable
- Forecast columns scored: `yhat_committed`, `snaive` (baseline)

## One yardstick across clusters (pooled over the folds)

| cluster | forecast | n_series | WMAPE % | bias % | median MASE | wMASE |
|---|---|---|---|---|---|---|
| … | committed | | | | | |
| … | snaive | | | | | |
| ALL | committed | | | | | |

**How to read:** WMAPE = currency error (gate metric); bias = net over/under; MASE < 1 = beats one-step naive for the typical series; wMASE weights the big series.

## Oracle ceiling
- Best-quantile-per-row WMAPE: `<x.x>` % · committed is `<d.d>` pts above the floor → *tuning headroom: <small / large>*.

## Readable vs strict gap

| cluster | forecast | readable % | strict % | gap pts | verdict |
|---|---|---|---|---|---|
| … | yhat_rules | | | | depends on serve-time-unknown drivers → off |

## Narrative
`<narrate_metrics output>`

## Decisions
- Quote: **strict** numbers.
- Clusters where committed does not beat the seasonal naive: `<list>` → served with the naive.
- Bias cap breached: `<list>` → business call on WMAPE-optimal vs bias-neutral blend.
