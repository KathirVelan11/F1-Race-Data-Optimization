# Real vs Predicted — Full 148-Race Sweep

How close are the models to what actually happened? For each race, "real" is the fastest driver who finished the full distance (DNFs excluded) — their actual total time, pit-stop count, and tyre sequence from the dataset. "Predicted" is what Model 1 (MILP, fastest) and Model 2 (Goal Programming, balanced) each calculated independently, with no knowledge of what really happened.

All 148 races across 2018–2024 were validated; both models solved to **Optimal** on every race except 2 transient solver failures (retried separately), leaving 147 Model 1 rows and 146 Model 2 rows in the results.

## Headline numbers

| Metric | Value |
|---|---|
| Races validated | 148 / 148 (2018–2024, full sweep complete) |
| Model 1 avg delta | +81.3s (36 / 147 beat the real fastest) |
| Model 2 avg delta | +67.4s (46 / 146 beat the real fastest) |
| Model 1 median delta | +84.9s (more robust than the mean) |
| Flagged outliers | 9 races |

Negative delta = model predicts a faster time than the real fastest finisher; positive = model predicts slower.

## Known data issue (9 of 148 races)

Red-flag or multi-safety-car races record the stoppage time as part of one lap's duration in the raw dataset (e.g. a 90s lap becomes a 3000s+ "lap"), inflating the real baseline. A >3× race-median lap-time filter removes most of this, but a few heavily-disrupted races still carry a residual skew:

- 2020 Bahrain Grand Prix
- 2020 Italian Grand Prix
- 2020 Tuscan Grand Prix
- 2022 Singapore Grand Prix
- 2023 Australian Grand Prix
- 2023 Azerbaijan Grand Prix
- 2023 São Paulo Grand Prix
- 2024 Japanese Grand Prix
- 2024 São Paulo Grand Prix

Excluding all flagged races, Model 1's average delta is **+39.4s**, vs. the unfiltered **+81.3s** across everything.

## Data

The full per-race, per-model comparison (year, race, model, real driver/time/stops/strategy, predicted time/stops, delta, beat-flag, outlier-flag) is kept as data rather than inlined here — see [`real_vs_predicted.csv`](real_vs_predicted.csv) (293 rows: up to 2 models × 148 races).

Source: `scripts/compare_to_real.py`, run against `scripts/validation_report.csv` (full 148-race run) and `data/processed/combined_dataset.csv`.
