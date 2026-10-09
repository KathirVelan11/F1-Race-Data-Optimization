# Model 1 vs Real Race Time

Model 1's predicted race time against the real winner's time, across the 10 races (of 109 sampled in the [Strategy Validation Sweep](strategy-validation-sweep.md)) where Model 1's solved strategy was faster than the actual fastest finisher, plus the 2 closest non-beating races for contrast.

| Year | Race | Real (s) | Model 1 (s) | Δ (M1 − Real) | Real winner |
|---|---|---|---|---|---|
| 2019 | Singapore GP | 7,113.67 | 7,094.96 | -18.71 | VET |
| 2020 | Emilia Romagna GP | 5,312.43 | 5,311.02 | -1.41 | HAM |
| 2020 | Russian GP | 5,640.36 | 5,622.82 | -17.54 | BOT |
| 2021 | Portuguese GP | 5,671.42 | 5,583.88 | -87.54 | HAM |
| 2022 | Australian GP | 5,266.55 | 5,198.33 | -68.22 | LEC |
| 2022 | Italian GP | 4,827.51 | 4,807.12 | -20.39 | VER |
| 2022 | Saudi Arabian GP | 5,059.29 | 5,052.46 | -6.83 | VER |
| 2023 | British GP | 5,116.94 | 5,034.60 | -82.34 | VER |
| 2023 | Japanese GP | 5,458.42 | 5,385.38 | -73.04 | VER |
| 2023 | Las Vegas GP | 5,348.29 | 5,333.56 | -14.73 | VER |
| 2023 | Saudi Arabian GP | 4,874.89 | 4,893.04 | +18.15 | PER |
| 2019 | Brazilian GP | 5,594.68 | 5,615.60 | +20.92 | VER |

Negative Δ = Model 1 faster than the real race winner. The first 10 rows are the races where Model 1 beat the real time; the last 2 are the closest races where it did not.

Source: `scripts/validation_random_results.csv` (109-race randomized validation sweep, seed 42).
