# Gate cycle report — `<model_name>` · run `<run_stamp>`

## Inputs
- Folds scored: `<list>` · scored rows `<n>` (min `<50>`)
- Champion: `<version>` (created `<date>`) · re-scored on current folds: `<x.xx>` %
- Gate: sigma `<2.0>` · std band = max(champion std, candidate std, `<0.5>`)

## Verdicts this run
| gate | verdict | candidate WMAPE | champion WMAPE | std | threshold | detail |
|---|---|---|---|---|---|---|
| refit_gate | | | | | | |
| staleness | | | | | | |
| challenger_gate | | | | | | |

## Outcome
- Promoted: `<yes/no>` as `<refit / challenger>` `<version>` · tuned this run: `<yes/no>` · alert: `<yes/no>`
- If alert: `<why the champion was kept; who reviews>`

## Registry (this model, latest rows)
| version | role | tuned | WMAPE | std | champion | created |
|---|---|---|---|---|---|---|

## Notes
- Tuning scope: `<blend weights + rule thresholds; LightGBM hyper-parameters frozen>`
- Per-cluster shadow gate: `<verdicts, if enabled>`
