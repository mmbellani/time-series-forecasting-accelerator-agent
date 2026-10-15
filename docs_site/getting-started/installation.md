# Installation

## Runtime

The pipeline runs on **Microsoft Fabric** or **Databricks** (Spark-based). Notebooks read and write tables through Spark and fall back to local Parquet.

## Clone

```bash
git clone https://github.com/mmbellani/time-series-forecasting-accelerator-agent.git
cd time-series-forecasting-accelerator-agent
```

## Python dependencies

```bash
pip install -r requirements.txt
```

!!! warning "Extra packages for some skills"
    Some skills need packages not yet in `requirements.txt`:
    `tslearn` (DTW clustering), `statsforecast` (moving-average / intermittent), `prophet`, `chronos`.
    See [Skills](../skills/index.md).

## Databricks

The repo includes a Databricks Asset Bundle config (`databricks.yml`) for deploying the notebooks to a workspace.
