# Intermittent Series

Intermittent series have many zero periods — common for slow-moving products, spare parts or insurance claims. Standard models handle them poorly, so the accelerator flags them during [Profiling](../pipeline/03-profiling.md).

## Indicators

A widely used classification (Syntetos–Boylan) uses two indicators:

$$
\text{ADI} = \frac{\text{number of periods}}{\text{number of non-zero demand periods}}
\qquad
\text{CV}^2 = \left(\frac{\sigma_{\text{non-zero}}}{\mu_{\text{non-zero}}}\right)^2
$$

| | CV² < 0.49 | CV² ≥ 0.49 |
|---|---|---|
| **ADI < 1.32** | Smooth | Erratic |
| **ADI ≥ 1.32** | Intermittent | Lumpy |

!!! note
    These are the standard textbook thresholds. Check notebook 03 for the parameters the accelerator actually uses.

## Typical profiles

| Profile | Description |
|---|---|
| Constant | Same value over time |
| Constant at zero | No demand |
| Unforecastable | Unpredictable timing **and** quantity |
| Spikes / lumpy / erratic | Irregular, high-variance demand |
| Regular | Suitable for standard ML forecasting |

## Forecasting intermittent series

Dedicated methods are not part of the core pipeline. Use the [Intermittent / Croston](../skills/forecasting-intermittent.md) skill (Croston, SBA, TSB, ADIDA, IMAPA).
