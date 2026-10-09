# Validation & Dataset Docs

These started as interactive HTML artifacts (claude.ai) for exploring validation results and dataset structure during this project's development. Their content has been converted into plain markdown docs so the repo is self-contained — no dependency on externally hosted pages.

## Validation results

- **[Strategy Validation Sweep](validation/strategy-validation-sweep.md)** — Solve-rate KPIs for Model 1/Model 2, and the full per-race table (real vs. Model 1 vs. Model 2 time/stops/risk/status) across a 109-race randomized validation run.

- **[Model 1 vs Real Race Time](validation/model1-vs-real-race-time.md)** — Model 1's predicted race time against the real winner's time, for the 10 races (of the 109-race sample) where Model 1 beat the real time plus the 2 closest non-beating races.

- **[Real vs Predicted](validation/real-vs-predicted.md)** — Full 148-race sweep comparing both models against the real fastest finisher per race, with a flagged-outlier callout for 9 races where red-flag/safety-car periods inflate a single lap's recorded duration in the raw data. Full per-race data in [`real_vs_predicted.csv`](validation/real_vs_predicted.csv).

- **[Validation Graph Options](validation/validation-graph-options.md)** — 6 candidate chart types (beat-rate summary, delta scatter, head-to-head bars, time-vs-risk tradeoff, pit-stop distribution, paired race comparison) built from the real 109-race sweep data.

## Dataset

- **[Dataset Merge Map](validation/dataset-merge-map.md)** — How `combined_dataset.csv` (161,443 rows) is built: which raw Kaggle/FastF1 files are used, and the 5-step join sequence.

## Early project brief (superseded)

- **[Early Project Brief](early-project-brief.md)** — An early brief proposing a different pair of optimizations (driver–constructor assignment via integer programming, plus a simpler pit-stop model) using the Ergast/Kaggle dataset directly. Superseded by the current, actually-implemented scope: Model 1 (MILP tyre/pit strategy) and Model 2 (Goal Programming), as described in the main [README](../README.md).
