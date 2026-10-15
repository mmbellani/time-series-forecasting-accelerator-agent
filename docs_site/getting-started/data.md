# Data Requirements

The pipeline works on **panel (long) data** — one row per series per date.

| Concept | Example column | Notes |
|---|---|---|
| Series id | `unique_id` / `STORE_LOCATION_ID` | Identifies each time series |
| Date | `ds` / `WEEK_START_DT` | Timestamp at a fixed frequency |
| Target | `y` / `TOTAL_NET_SALES` | Value to forecast |
| Grouping | `profile_cluster` | Added by notebooks 03 / 04 |

Column names are configurable at the top of each notebook.

```text
unique_id | ds         | y
----------+------------+--------
store_001 | 2025-01-06 | 1520.40
store_001 | 2025-01-13 | 1488.10
store_002 | 2025-01-06 |  905.75
```

!!! note "Not energy or retail data?"
    The method is domain-agnostic: any set of regularly sampled series in this long format works.
