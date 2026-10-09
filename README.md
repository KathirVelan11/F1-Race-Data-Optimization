# F1 Race Strategy & Performance Optimization

Operational Research course project (Team B13). Models Formula 1 pit
stop strategy as an optimization problem, using historical race data
to find and validate optimal tyre/pit decisions.

## Problem statement

Given a Formula 1 race of fixed lap distance, the tyre compounds
actually used in that race's historical data (any of Soft, Medium,
Hard, Intermediate, Wet, plus the legacy 2018-only compounds
Ultrasoft/Supersoft/Hypersoft), each with a different degradation
rate, and a pit-stop time cost derived from that race/circuit's real
pit-stop data — how many pit stops should the driver make, on which
specific laps should each stop occur, and which tyre compound should
be fitted for each resulting stint, such that total race time (lap
times + pit-stop time lost) is minimized?

Pit-stop cost, compound durability, and compound base pace are all
computed per-race from the real dataset rather than fixed constants —
a pit stop at a track like Monaco costs noticeably more track time
than one at a low-pit-loss circuit, soft compounds degrade faster
than hard ones, and legacy 2018 compounds only appear in 2018 races.
Strategy differences of 1–2 seconds have decided real race wins and
championships.

## Approach

Two optimization models answer two related questions.

### Model 1 — Tyre & Pit-Stop Strategy (MILP)

"What's the single fastest possible strategy?" — no other
considerations, pure minimum race time.

**Sets** — `l ∈ {1,...,N}` laps; `c ∈ C` tyre compounds, where `C` is
whichever compounds actually appear in that race's real data
(typically a subset of Soft/Medium/Hard/Intermediate/Wet, or the 2018
legacy compounds Ultrasoft/Supersoft/Hypersoft).

**Decision variables**
- `x[l,c]` ∈ {0,1} — 1 if compound `c` is used on lap `l`
- `p[l]` ∈ {0,1} — 1 if a pit stop occurs after lap `l`

**Parameters**
- `T[l,c]` — predicted lap time on compound `c` at current tyre age,
  derived from real per-compound lap times for that race
- `P` — pit-stop time loss, derived from real pit-stop durations for
  that race (falling back to the circuit's or dataset's mean if the
  race has too little data)
- `L_max[c]` — maximum durable stint length for compound `c`, derived
  from real tyre-life data for that race (falling back to the
  dataset-wide mean)
- `N` — total race laps
- `min_pit_stops`, `min_stint_length`, `max_sets_per_compound` —
  user-adjustable inputs, validated against data-derived valid ranges
  per race so an out-of-range value (too low, too high) can't make the
  model infeasible or unrealistic. Model 1 has no pit-stop *ceiling* —
  only Model 2 does (see below).

**Objective**

```
min T_race = Σ(l=1..N) T[l,c] + P · Σ(l=1..N) p[l]
```

**Constraints**
- exactly one compound active per lap: `Σ_c x[l,c] = 1`, ∀l
- at least `min_pit_stops` pit stops: `Σ_l p[l] ≥ min_pit_stops`
- tyre age can't exceed the compound's durability limit: `TyreAge[l,c] ≤ L_max[c]`
- minimum stint length ≥ `min_stint_length` laps
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

**Additional inputs (Model 2 only)**
- `max_pit_stops` — user input, enforced as a genuine hard ceiling on
  total pit stops (on top of the shared `min_pit_stops` floor), and
  used directly as Goal 2's target `P*`. Must be ≥ `min_pit_stops`; a
  request violating that is rejected with a clear message rather than
  silently clamped. Left blank, it defaults to `min_pit_stops` itself.
- `max_risk_tier_per_compound` — optional, per-compound absolute hard
  ceiling on degradation-risk tier, independent of weights/targets.

**Additional variables**: `d1+, d1-, d2+, d2-, d3+, d3-` — deviation
variables, how far a strategy over/under-achieves each goal, each
normalized by its own target so they're comparable fractions (0 = on
target) rather than raw units of different scale.

**Goals** — all three targets are "best achievable" values, not
arbitrary or historical ones:
```
Goal 1 (Time):   T/T* + d1- - d1+ = 1   (T* = Model 1's solved fastest time)
Goal 2 (Stops):  P/P* + d2- - d2+ = 1   (P* = the user's max_pit_stops input, directly)
Goal 3 (Risk):   R/R* + d3- - d3+ = 1   (R = total degradation-risk score, sum of
                                          per-lap risk-tier weights 0=low..3=very high;
                                          R* = the true minimum R achievable under this
                                          race's constraints, found via a dedicated
                                          minimize-R solve before the real balanced solve)
```

**Objective**
```
min Z = w1·d1+ + w2·d2+ + w3·d3+
```
Only overshoot (`d+`) is penalized — beating a target is always free.
Default weights: `w1 = 0.50, w2 = 0.25, w3 = 0.25` (user-adjustable,
must sum to 1). See `docs/mathematical-models/scope2_goal_programming.md`
for the full derivation and rationale.

**Output**: a strategy that accepts a small race-time increase in
exchange for fewer pit stops / lower tyre degradation, per the team's
weights. e.g. Model 1 → 1:28:33.2, Model 2 → 1:28:35.1 (+1.9s, same
stints, adjusted timing).

## Interface

- React/Vite frontend talking to a FastAPI backend (see `frontend/`
  and `backend/`)
- Dataset overview panel: races per year, compound usage, mean max
  stint life per compound, pit-stop stats — generated on demand from
  the real dataset
- User picks season/race/driver, sets strategy constraints
  (min/max pit stops, min stint length, tyre-set and risk-tier limits)
  within data-derived valid ranges, and tunes Model 2's goal-priority
  weights (must sum to 1)
- Tabs for Model 1 (fastest strategy) and Model 2 (balanced strategy),
  each showing the recommended pit laps, compound per stint, a
  pit-stop-by-stop breakdown, and predicted race time (Model 2 also
  shows its goal targets)

## Validation

`scripts/validate_models.py` runs both models across all 148 races in
the dataset and sanity-checks the solver output (lap coverage, stint
validity, solver status). `scripts/compare_to_real.py` re-solves both
models per race and compares the predicted strategy/time against the
real fastest finisher's actual strategy/time for that race.

## Status

- [x] Data collection & merge pipeline (`scripts/build_dataset.py`)
- [x] Model 1 — MILP tyre/pit-stop optimizer
- [x] Model 2 — Goal Programming balanced strategy
- [x] Interface (FastAPI backend + React/Vite frontend)
- [x] Validation against actual race results (`scripts/validate_models.py`, `scripts/compare_to_real.py`)

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
