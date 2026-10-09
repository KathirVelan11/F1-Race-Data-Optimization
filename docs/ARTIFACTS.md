# Published Artifacts

Interactive HTML artifacts created on claude.ai during this project's development, for exploring validation results and dataset structure. These are supplementary/working visualizations, not part of the shipped application (`frontend/` + `backend/`) or its build.

Links are private-by-default Claude Artifacts owned by Kathir Velan M.

## Validation results

- **[Strategy Validation Sweep](https://claude.ai/artifact/Bsj7D6xEFcNevuAK8ZGW9V)** — Interactive dashboard over a 109-race randomized validation run: solve-rate KPIs for Model 1/Model 2, a time-delta-vs-real scatter plot, a per-race strategy comparison picker (real vs. Model 1 vs. Model 2 stints side by side), and a sortable/searchable table of all 109 races. Source data: `scripts/validation_random_results.csv`.

- **[Model 1 vs real race time](https://claude.ai/artifact/Bit9hy8qzkjrrZnV7XftBv)** — Line chart comparing Model 1's predicted race time against the real winner's time, for the 10 races (of the 109-race sample) where Model 1 beat the real time plus the 2 closest non-beating races.

- **[Real vs predicted](https://claude.ai/artifact/8cs4VnV7qKnd6czJ1zk61E)** — Full 148-race sweep comparing both models against the real fastest finisher per race (driver, time, pit stops, strategy), filterable by model/year, with a flagged-outlier callout for 9 races where red-flag/safety-car periods inflate a single lap's recorded duration in the raw data. Model 1 avg delta +81.3s (36/147 beat real), Model 2 avg delta +67.4s (46/146 beat real). Source: `scripts/compare_to_real.py` output, `real_vs_predicted.csv`.

- **[Validation Graph Options](https://claude.ai/artifact/RRd6SygzubFMSQBf8GAQxV)** — A gallery of 6 candidate chart types (beat-rate summary, delta scatter, head-to-head bars, time-vs-risk tradeoff scatter, pit-stop count distribution, paired race comparison) built from the real 109-race sweep data, for choosing how to present Model 1 vs. real and Model 1 vs. Model 2 results.

## Dataset

- **[F1 Dataset Merge Map](https://claude.ai/artifact/2npWhpJEgQFd9zr3Y9iiWL)** — Visual walkthrough of how `combined_dataset.csv` (161,443 rows) is built: which raw Kaggle/FastF1 files are used, and the 5-step join sequence (driver codes → race year/name → core Kaggle×FastF1 fusion on `(year, race, driver, lap)` → pit-stop duration → team name).

## Early project brief (superseded)

- **[Grid Theory — F1 Optimization Project Brief](https://claude.ai/artifact/Jjvan4m64roRBQ8hJtt462)** — An early project brief proposing a different pair of optimizations (driver–constructor assignment via integer programming, plus a simpler pit-stop model) using the Ergast/Kaggle dataset directly. Superseded by the current, actually-implemented scope: Model 1 (MILP tyre/pit strategy) and Model 2 (Goal Programming), as described in the main [README](../README.md).
