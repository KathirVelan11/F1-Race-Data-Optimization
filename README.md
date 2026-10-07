# F1 Race Strategy & Performance Optimization

Operational Research course project (Team B13). Models Formula 1 pit
stop strategy as an optimization problem, using historical race data
to find and validate optimal tyre/pit decisions.

## Problem statement

Given a Formula 1 race of fixed lap distance, three tyre compounds
(Soft, Medium, Hard) each with a different degradation rate, and a
fixed time cost per pit stop — how many pit stops should the driver
make, on which specific laps should each stop occur, and which tyre
compound should be fitted for each resulting stint, such that total
race time (lap times + pit-stop time lost) is minimized?

A pit stop costs roughly 20 seconds of track time but resets tyre
performance. Soft tyres are fastest but degrade in ~15–25 laps,
Medium balances grip and durability (~25–40 laps), Hard lasts longest
(~40–50+ laps) but is slowest. Strategy differences of 1–2 seconds
have decided real race wins and championships.

## Approach

Two optimization models answer two related questions.

### Model 1 — Tyre & Pit-Stop Strategy (MILP)

"What's the single fastest possible strategy?" — no other
considerations, pure minimum race time.

**Sets** — `l ∈ {1,...,N}` laps; `c ∈ {S,M,H}` tyre compounds.

**Decision variables**
- `x[l,c]` ∈ {0,1} — 1 if compound `c` is used on lap `l`
- `p[l]` ∈ {0,1} — 1 if a pit stop occurs after lap `l`

**Parameters**
- `T[l,c]` — predicted lap time on compound `c` at current tyre age
- `P` — fixed pit-stop time loss (≈ 13 seconds)
- `L_max[c]` — maximum durable stint length for compound `c`
- `N` — total race laps

**Objective**

```
min T_race = Σ(l=1..N) T[l,c] + P · Σ(l=1..N) p[l]
```

**Constraints**
- exactly one compound active per lap: `Σ_c x[l,c] = 1`, ∀l
- at most 2 pit stops per race: `Σ_l p[l] ≤ 2`
- tyre age can't exceed the compound's durability limit: `TyreAge[l,c] ≤ L_max[c]`
- minimum stint length ≥ 5 laps
- stints must cover the full race distance: `Σ_i stint[i] = N`
- `x[l,c], p[l] ∈ {0,1}`

**Output**: the exact pit laps, the tyre compound for each stint, and
the minimum predicted total race time.

### Model 2 — Multi-Objective Strategy (Goal Programming)

Real teams rarely optimize on time alone — they also want to limit
pit-stop count (each one is a risk of error), reduce tyre degradation,
and keep overall strategic risk low. This model finds the single
strategy that best balances all of these, trading a small amount of
race time for fewer pit stops / less degradation, based on
team-assigned priority weights.

**Additional variables**: `d1+, d1-, d2+, d2-, d3+, d3-` — deviation
variables, how far a strategy over/under-achieves each goal.

**Goals** (targets set from Model 1's result and team preference)
```
Goal 1 (Time):        T + d1- - d1+ = T*   (T* = fastest time, from Model 1)
Goal 2 (Pit stops):   P + d2- - d2+ = P*   (e.g. P* = 2 stops)
Goal 3 (Degradation): D + d3- - d3+ = D*   (target degradation rate)
```

**Objective**
```
min Z = w1·d1+ + w2·d2+ + w3·d3+
```
Example weights: `w1 = 0.50, w2 = 0.25, w3 = 0.25`.

**Output**: a strategy that accepts a small race-time increase in
exchange for fewer pit stops / lower tyre degradation, per the team's
weights. e.g. Model 1 → 1:28:33.2, Model 2 → 1:28:35.1 (+1.9s, same
stints, adjusted timing).

## Planned interface

- Load race data, generate statistics on demand (tyre degradation
  curves, pit-stop cost breakdowns)
- User chooses which model to run: Model 1 (fastest) or Model 2
  (balanced)
- Output: recommended pit laps + compound per stint, and predicted
  race time

## Validation

Predicted race time is compared against the actual race result
(Kaggle `results.csv`) to report prediction accuracy.

## Status

- [x] Data collection & merge pipeline (`scripts/build_dataset.py`)
- [ ] Model 1 — MILP tyre/pit-stop optimizer
- [ ] Model 2 — Goal Programming balanced strategy
- [ ] Interface
- [ ] Validation against actual race results

## Data

- `data/raw/kaggle/` — raw Kaggle F1 tables (races, results, pit stops,
  lap times, drivers, constructors, etc.), 1950–2024. Source:
  [Formula 1 World Championship (1950-2020)](https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020)
  on Kaggle.
- `data/raw/fastf1/` — flat per-lap FastF1 extracts (tyre compound,
  tyre age, stint) for 2018–2024. Source:
  [FastF1](https://theoehrly-fast-f1.mintlify.app/) Python API.
- `data/processed/combined_dataset.csv` — the master dataset: Kaggle
  lap times/pit stops/results merged with FastF1 tyre data, lap by lap.

## Setup

```
pip install -r requirements.txt
```

## Final dataset structure (`combined_dataset.csv`)

161,443 rows, one row per driver per lap.

| Column         | Type    | Description |
|----------------|---------|-------------|
| `raceId`       | int     | Kaggle's unique race identifier |
| `Year`         | int     | Season year |
| `Race`         | string  | Grand Prix name |
| `Driver`       | string  | 3-letter driver code (e.g. `VER`, `HAM`) |
| `Team`         | string  | Constructor/team name |
| `Lap`          | int     | Lap number within the race |
| `LapTime`      | string  | Lap time, `M:SS.sss` (e.g. `1:28.176`) |
| `Position`     | int     | Driver's race position after that lap |
| `Compound`     | string  | Tyre compound used that lap (`SOFT`, `MEDIUM`, `HARD`, `INTERMEDIATE`, `WET`, plus historical compounds `ULTRASOFT`/`SUPERSOFT`/`HYPERSOFT` used pre-2019) |
| `TyreLife`     | float   | Age of the current tyre set, in laps |
| `Stint`        | float   | Stint number (1st, 2nd, 3rd set of tyres used in the race) |
| `pit_duration` | float   | Pit stop duration in seconds, only set on the lap a pit stop happened (5,098 of 161,443 rows); `NaN` otherwise |

40 unique drivers, 16 unique teams, 148 unique races across all years.

## Coverage per year

| Year | Races | Rows |
|------|-------|------|
| 2018 | 20    | 21,320 |
| 2019 | 21    | 23,625 |
| 2020 | 17    | 18,321 |
| 2021 | 22    | 23,688 |
| 2022 | 22    | 23,529 |
| 2023 | 22    | 24,386 |
| 2024 | 24    | 26,574 |

All seasons are complete (2020's 17 races and the rest reflect the
real-world F1 calendar those years, not missing data).

## Rebuilding the dataset

```
python scripts/build_dataset.py
```

Reads only `data/raw/`, writes `data/processed/combined_dataset.csv`.
No intermediate files, no network access required.
