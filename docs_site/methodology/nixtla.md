# Nixtla Framework

Modelling uses Nixtla's **`mlforecast`**, which trains gradient-boosting models across many series at once.

Key idea: **one global model for many series**, with features declared once and computed consistently for training and forecasting.

```python
from mlforecast import MLForecast
from mlforecast.lag_transforms import RollingMean
import lightgbm as lgb

fcst = MLForecast(
    models=[lgb.LGBMRegressor()],
    freq="W-MON",
    lags=[1, 4, 52],
    lag_transforms={1: [RollingMean(window_size=4)]},
    date_features=["month", "week"],
)
fcst.fit(train_df)              # columns: unique_id, ds, y
preds = fcst.predict(h=12)
```

!!! note
    Illustrative example — see notebooks 05 and 06 for the exact configuration.

Related libraries used by skills: `statsforecast` (statistical and intermittent models).
