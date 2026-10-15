# Panel preparation report — `<scenario>`

## Source
- Raw table: `<name>` · extracts present: `<n>` · extract used: `<id>` (`<Job-provided / latest by timestamp>`)
- Timestamp column: `<col>` parsed as UTC → naive month start

## Grid
- Series: `<n>` · months: `<first>` → `<last>` · rows after gap filling: `<n>`
- Zero-quantity share of series-months: `<x %>` (expected for intermittent demand)
- `price_per_unit` NaN rows (credit notes / revenue without quantity): `<n>`

## Trailing-edge coverage (active series / steady state)
| month | coverage | decision |
|---|---|---|
| `<m-2>` | | keep |
| `<m-1>` | | keep |
| `<m>` | | **drop** (< `<90>` %) → DATA_MAX = `<m-1>` |

## Leak check (lag 2)
| table | corr(y, lag2) | share of rows where lag2 == y |
|---|---|---|
| stacked extracts | | |
| pinned extract | | ~0 |

## Decisions
- DATA_MAX: `<date>` · dropped months: `<list>` · pinned extract recorded in the run log.
