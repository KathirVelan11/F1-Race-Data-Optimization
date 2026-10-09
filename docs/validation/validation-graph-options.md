# Validation Graph Options

Candidate chart types considered for presenting Model 1 vs. real and Model 1 vs. Model 2 validation results, built from the actual 109-race sweep (`scripts/validation_random_results.csv`, seed 42), not mock data.

**Caveat that applies to every "vs. real" chart below:** a real race's finishing time isn't ground truth to match exactly — safety cars, traffic, team orders, and risk tolerance all shape what a driver actually did. The claim a "vs. real" chart should support is *"under the constraints we assumed, our strategy is at least as good,"* not *"we replicated history."*

## 1. Beat-rate summary (M1 vs real)

**Best for:** the headline claim, top of a results page.

Leads with one number: how often Model 1 matched or beat the real race time.

- **10 of 109 races** (~9%) — Model 1 matched or beat the real finishing time.

Read as: "In most races, M1's assumed-scenario time runs slightly over the real time — because the real driver had information and track conditions our model doesn't model (fuel load strategy, live gaps, safety car timing). The races where M1 matched or beat it show the model finding a genuinely stronger strategy under the same tyre/stint rules."

## 2. Delta scatter (M1 vs real)

**Best for:** a detail view under the headline stat, or an appendix slide.

Every race as one point: seconds slower (positive) or faster (negative) than the real finishing time, across all 109 races. See the full distribution in the [Strategy Validation Sweep](strategy-validation-sweep.md) table (M1 Δ column) and the [Model 1 vs Real Race Time](model1-vs-real-race-time.md) doc for the beating/closest races specifically.

## 3. Head-to-head bars (M1 vs M2)

**Best for:** explaining the time/risk tradeoff Model 2 makes.

Direct Model 1 vs. Model 2 comparison, no real-race baseline involved — the pure "what does balancing cost you in time" question. Sample of Model 2's time penalty vs. Model 1 (seconds; negative = M2 faster) for the first 25 races in sweep order:

```
13.9, 22.2, 281.2, 5.8, 34.6, -26.9, 16.7, 2.6, 0.2, 61.8,
35.1, 13.2, 133.5, 8.4, 0.0, 38.8, 0.0, 10.3, 149.5, 13.8,
14.4, 39.8, 100.0, -48.5, -62.6
```

## 4. Time-cost vs. risk-score scatter (M1 vs M2)

**Best for:** justifying Model 2 as a genuine trade-off, not just "slower."

Plots what Model 2 actually buys: x-axis is extra seconds vs. Model 1, y-axis is the resulting degradation-risk score. Points low-left are the efficient trade-offs — small time cost, low risk. Full per-race time-cost and risk-score series are in the [Strategy Validation Sweep](strategy-validation-sweep.md) table (M2 Δ and M2 Risk columns).

## 5. Pit-stop count distribution (Real / M1 / M2)

**Best for:** a quick "how do the models actually behave differently" visual.

Three-way histogram of pit-stop counts across all races — shows that Model 1 tends to pit more (chasing pace) while Model 2 tends to pit less (fewer tyre changes lowers cumulative risk exposure).

| Pit stops | Real | Model 1 | Model 2 |
|---|---|---|---|
| 0 | 0 | 1 | 35 |
| 1 | 45 | 18 | 36 |
| 2 | 48 | 62 | 28 |
| 3 | 12 | 18 | 9 |
| 4 | 3 | 8 | 1 |
| 5 | 1 | 2 | 0 |

## 6. Paired race comparison (Real + M1 + M2)

**Best for:** a "here's what this actually looks like" section, right after the summary charts — a worked example rather than a summary chart.

| Year | Race | Real (s) | Model 1 (s) | Model 2 (s) | M2 risk score |
|---|---|---|---|---|---|
| 2019 | Belgian Grand Prix | 4,980.75 | 5,096.74 | 5,110.67 | 24 |
| 2019 | Azerbaijan Grand Prix | 5,512.94 | 5,649.25 | 5,671.45 | 39 |
| 2019 | Bahrain Grand Prix | 5,661.30 | 5,757.52 | 6,038.76 | 55 |
| 2019 | Canadian Grand Prix | 5,345.74 | 5,487.39 | 5,493.16 | 50 |
| 2019 | Australian Grand Prix | 5,127.32 | 5,256.25 | 5,290.84 | 16 |

(First 5 races of the sweep; the full 109-race set is in the [Strategy Validation Sweep](strategy-validation-sweep.md) table.)

---

These are rendering options, not a final report — the underlying fields all exist in `scripts/validation_random_results.csv` for building whichever of these (or combination) best fits the UI.
