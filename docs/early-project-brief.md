# Early Project Brief (Superseded)

> **Note:** This was an early project brief proposing a different pair of optimizations than what was actually built. It's kept here for history only — the current, implemented scope is Model 1 (MILP tyre/pit strategy) and Model 2 (Goal Programming), described in the main [README](../README.md). The driver–constructor assignment idea below was dropped entirely.

## Grid Theory: Optimizing Driver Pairings & Pit Strategy in Formula 1

*Operations Research — Group Project Brief.* An applied optimization study on 75 years of championship data — one dataset, two decisions: who should drive for whom, and when a car should stop.

- **Domain:** Motorsport — Formula 1
- **Dataset:** Ergast F1 World Championship, 1950–2024
- **Techniques:** Assignment Problem · Integer Programming

### The dataset

**Formula 1 World Championship (1950–2024)**, compiled and maintained by Kaggle user Vopani from the open Ergast Developer API (ergast.com/mrd), is released under a CC0: Public Domain license. [kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020](https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020)

Fourteen linked CSV tables:

| Table | What it holds | Proposed use |
|---|---|---|
| drivers.csv | Driver identity & nationality | Optimization 1 |
| constructors.csv | Team (constructor) identity | Optimization 1 |
| results.csv | Every driver's result, every race | Optimization 1 |
| driver_standings.csv | Championship points & wins per race | Optimization 1 |
| constructor_standings.csv | Team points & wins per race | Optimization 1 (support) |
| pit_stops.csv | Real recorded pit-stop lap & duration | Optimization 2 |
| lap_times.csv | Real recorded lap time, every lap | Optimization 2 |
| races.csv | Race calendar, circuit, date | Optimization 2 (selector) |
| circuits.csv | Track location, layout metadata | Dashboard stats |
| qualifying.csv | Grid-deciding session results | Dashboard stats |
| status.csv, seasons.csv, constructor_results.csv, sprint_results.csv | Supporting reference tables | Dashboard stats |

### Optimization 1 (proposed, not built): Driver–Constructor Assignment

**The real decision:** every off-season, free-agent drivers are paired with teams — each team fields exactly two cars. Which complete pairing, across the whole grid at once, produces the best combined outcome?

**Formulation:**
```
x[i][j] ∈ {0, 1}               // 1 if driver i joins constructor j

maximize  Σ_i Σ_j  score[i][j] · x[i][j]

Σ_j x[i][j] = 1     for every driver i        // one team per driver
Σ_i x[i][j] = 2     for every constructor j   // two drivers per team
```

**Worked example** (4 drivers, 2 teams, historical avg points/race if racing for that team):

| | Team A | Team B |
|---|---|---|
| Driver 1 | 18 | 10 |
| Driver 2 | 15 | 12 |
| Driver 3 | 8 | 14 |
| Driver 4 | 6 | 9 |

Best pairing: Drivers 1 & 2 → Team A, Drivers 3 & 4 → Team B (33 + 23 = 56 points combined).

### Optimization 2 (proposed precursor to the actual Model 1/Model 2): Pit-Stop Strategy

**The real decision:** on which laps should a car stop, so total race time is as low as possible?

**Formulation:**
```
y[lap] ∈ {0, 1}   for lap = 1 … total race laps

minimize  Σ_lap ( lapTime[lap] + y[lap] · avgPitDuration )
   where lapTime[lap] rises with laps-since-last-stop

Σ_lap y[lap] ≥ 1    // minimum one stop — real tyre regulation
Σ_lap y[lap] ≤ 4    // realistic ceiling, drawn from observed stop counts
```

Illustrative example figures: avg. pit duration 22.1s, degradation +0.15s/lap (from `pit_stops.csv` and `lap_times.csv`).

**Worked example** (50-lap race):

| Plan | Pit cost | Degradation cost | Total |
|---|---|---|---|
| 0 stops | 0.0s | 187.5s | 187.5s |
| 1 stop (lap 25) | 22.1s | 93.8s | 115.9s |
| 2 stops (laps 17, 34) | 44.2s | 62.5s | **106.7s** |

### Why this approach was proposed

- Genuinely different problems — a matching question vs. a scheduling question, not two variations of the same model.
- No external data required — every score/cost figure derivable from one Kaggle download.
- Traceable — every number points back to an exact column in an exact file.

### What actually got built instead

The project moved away from the driver-assignment idea entirely and instead built two models both focused on race strategy: Model 1 (MILP, fastest possible tyre/pit-stop strategy) and Model 2 (Goal Programming, balancing time against pit-stop count and tyre-degradation risk) — using the merged Kaggle + FastF1 dataset described in [Dataset Merge Map](validation/dataset-merge-map.md), not the Ergast CSVs directly. See the main [README](../README.md) and [Methodology section](../README.md#methodology) for the full current design.
