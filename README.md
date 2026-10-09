# F1 Race Strategy & Performance Optimization

Operational Research course project (Team B13: Pranesh L, Kathir Velan M,
Sasi Kumar P, Jeiesh S). Models Formula 1 pit stop strategy as an
optimization problem, using historical race data to find and validate
optimal tyre/pit decisions.

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

---

# Methodology

This section explains, from the ground up, how this project turns raw
Formula 1 timing data into an optimized race strategy. It is written
for a reader who has never seen the code before. Every formula is
explained in words before it is written in symbols, and every symbol
used is defined where it first appears.

Both models are built and solved using a Python optimization library
called PuLP, which lets us write down a mathematical model (decision
variables, an objective to minimize, and a list of constraints) and
hand it to a solver (HiGHS, with CBC as a backup) that searches for the
best possible answer. Everything the models need to know — how fast
each tyre compound is, how quickly it wears out, how much time a pit
stop costs — is calculated directly from real historical race data,
not guessed.

### Table of Contents

1. [The Real-World Problem](#1-the-real-world-problem)
2. [Where the Data Comes From](#2-where-the-data-comes-from)
3. [Turning Raw Data Into Model Inputs](#3-turning-raw-data-into-model-inputs)
4. [Model 1: Finding the Fastest Possible Strategy](#4-model-1-finding-the-fastest-possible-strategy)
5. [Model 2: Finding a Balanced, Realistic Strategy](#5-model-2-finding-a-balanced-realistic-strategy)
6. [How Tyre Wear Risk Is Measured](#6-how-tyre-wear-risk-is-measured)
7. [How the Solver's Answer Becomes a Strategy](#7-how-the-solvers-answer-becomes-a-strategy)
8. [Checking Feasibility Before Solving](#8-checking-feasibility-before-solving)
9. [How Model 1 and Model 2 Work Together](#9-how-model-1-and-model-2-work-together)
10. [Checking the Models Against Real Races](#10-checking-the-models-against-real-races)
11. [A Worked Example With Real Numbers](#11-a-worked-example-with-real-numbers)
12. [Full List of Symbols Used](#12-full-list-of-symbols-used)

---

## 1. The Real-World Problem

In a Formula 1 Grand Prix, a car has to complete a fixed number of laps around a circuit — usually somewhere between 50 and 70, depending on the track. The rules require every driver to use at least two different types of dry-weather tyre during the race, which means every driver must stop at the pits at least once to change tyres.

There are three main types of dry tyre, each a trade-off between speed and durability:

- **Soft** tyres grip the track the hardest and produce the fastest lap times, but they wear out quickly.
- **Medium** tyres are a balance — not as fast as Soft, but they last longer.
- **Hard** tyres are the slowest of the three per lap, but they can run for a very long time before wearing out.

(The exact names used for compounds have changed over the years — in 2018, for example, Formula 1 used five compound names, from Hypersoft through to Hard; from 2019 onward it settled into the simpler Soft/Medium/Hard naming most fans know today. Wet-weather races also use Intermediate and Wet tyres. The project reads whichever compound names actually appear in a given race's data, rather than assuming fixed names.)

A tyre's lap time also gets slower the longer it has been used — this is called **degradation**. A fresh tyre is fast; the same tyre after 20 laps of hard use is noticeably slower.

Every time a car comes into the pits to change tyres, it loses real time on track — it has to slow down, enter the pit lane, come to a stop, have all four tyres changed, and rejoin the race. Depending on the circuit, this costs somewhere between about 13 and 30 seconds compared to staying out on track.

So a race engineer planning a strategy has to decide:

1. How many times to stop for new tyres.
2. On exactly which lap to make each stop.
3. Which tyre compound to fit after each stop.

And they have to balance two competing goals: going as fast as possible, versus not taking unnecessary risks (an extra pit stop is an extra chance for something to go wrong in the pit lane, and an old, worn tyre is more likely to suddenly lose grip or fail).

This project builds two optimization models to answer this decision problem, both driven entirely by real historical F1 data:

- **Model 1** ignores the risk trade-off entirely and simply finds whatever strategy produces the lowest total race time.
- **Model 2** takes that same question but adds the realistic trade-offs — it is willing to accept a small time penalty in exchange for fewer pit stops and safer tyre usage, weighted according to how much the user cares about each of those three things.

---

## 2. Where the Data Comes From

The project uses two publicly available sources of historical Formula 1 data, which are merged together into one combined dataset:

- A **Kaggle historical database**, which covers every Formula 1 race since 1950 and includes race results, lap times, and pit stop records.
- **FastF1 telemetry data**, a more detailed, lap-by-lap data source covering the 2018–2024 seasons, which records exactly which tyre compound was on the car each lap, how old that tyre was (in laps), and which "stint" (the period between pit stops) each lap belonged to.

These two sources are combined into a single master file: `data/processed/combined_dataset.csv`. It has one row for every lap driven by every driver, across every race from 2018 to 2024 — about 161,000 rows in total. Each row records, among other things:

- which year and race the lap belongs to,
- which driver and team,
- the lap number,
- the actual lap time (e.g. "1:28.176"),
- which tyre compound was fitted,
- how many laps old that tyre was,
- which stint (pit-stop period) the lap belongs to,
- and, if that lap included a pit stop, how long the stop took.

This combined file is treated as a finished, trustworthy dataset — the project never rebuilds or edits it during normal use. All parts of the system read from it through a single, shared piece of code (the "dataset loader"), so there's only one place responsible for correctly loading and filtering this data.

Lap times are stored as text in the format minutes:seconds (for example `"1:28.176"` means one minute and 28.176 seconds). A small utility function converts this text into a plain number of seconds wherever the models need to do arithmetic with it, by reading an optional minutes part followed by a required seconds part.

---

## 3. Turning Raw Data Into Model Inputs

Before either model can run, the system needs to work out several numbers from the real race data: how fast each tyre compound is, how quickly it degrades, how much a pit stop costs at this particular circuit, and how long a tyre can safely last. Nothing here is a textbook assumption — every one of these numbers is calculated directly from the actual lap times and pit stops recorded for the selected race (falling back to data from other races only when the selected race doesn't have enough of its own).

### 3.1 Which tyre compounds are actually available

The system looks at which compound names actually appear in the chosen race's data, removes anything meaningless (blank values, "unknown", etc.), and sorts them from softest to hardest using the real Pirelli compound hierarchy (Hypersoft, Ultrasoft, Supersoft, Soft, Medium, Hard, Intermediate, Wet). This means the set of usable compounds is specific to each individual race, rather than being hard-coded as always "Soft, Medium, Hard" — a 2018 race might offer Hypersoft/Supersoft/Soft, while a 2023 race offers Soft/Medium/Hard.

### 3.2 How fast each compound is when fresh — the baseline pace

For every compound, the system calculates the *average* lap time recorded on that compound, preferring laps from this exact race first (because lap time is mostly determined by how long and how fast the specific circuit is — a lap at Monaco takes about 82 seconds, while the average Soft-tyre lap time across every circuit in the whole dataset is closer to 97 seconds, so using the whole dataset's average for a Monaco race would be badly wrong). If the chosen race doesn't have enough laps on a particular compound, the system falls back to that compound's average across the entire multi-year dataset, and only as a last resort falls back to the average lap time across all compounds combined.

Call this baseline pace for compound $c$ simply "Base of $c$" — it represents how fast that tyre runs on lap 1, before any wear has happened.

### 3.3 How quickly each compound slows down — the degradation rate

The system fits a straight line through real data: lap time versus tyre age (in laps), for every lap recorded on a given compound. This is ordinary linear regression — the same statistical method used to find a "line of best fit" through a scatter of points. The slope of that line tells us, on average, how many extra seconds a lap takes for every additional lap of tyre age. The intercept of that line (where it crosses zero tyre age) is used as a cross-check against the baseline pace described above.

Two safety rules are applied to this fit:

- If a compound doesn't have at least 5 recorded laps with at least two different tyre ages, there isn't enough information to fit a reliable line, so the system falls back to the dataset-wide fit for that compound, and ultimately to a degradation rate of zero (meaning "assume no wear effect") only if there's truly no usable data anywhere.
- The slope is never allowed to come out negative. Physically, a tyre cannot get *faster* as it wears — if the raw statistical fit produces a negative number, that's a sign the result is being distorted by something else (cars get lighter and faster as they burn off fuel over a race, or traffic from other cars slows a lap down), not a real sign of tyres improving with age. So any negative result is floored at zero.

Call this degradation rate for compound $c$ "Degradation rate of $c$," measured in seconds lost per lap of tyre age.

### 3.4 Predicting the lap time for any lap and any compound

Combining the two numbers above, the predicted lap time for lap number $l$ on compound $c$ is simply:

$$
T_{l,c} = \text{Base of } c \;+\; (\text{Degradation rate of } c) \times l
$$

In words: the baseline pace for that compound, plus the degradation rate multiplied by how many laps into its life the tyre is. This table of predicted lap times (one number for every combination of lap and compound) is what both optimization models use to judge how fast any given strategy would be. The models themselves are responsible for correctly resetting a tyre's "age" to zero whenever a pit stop happens, so a compound's effective age is always counted from the start of its current stint, not from the start of the race.

The project deliberately uses this smooth, fitted curve rather than the raw, noisy lap-by-lap averages, because real lap times bounce around for reasons that have nothing to do with tyre wear — changing fuel load, traffic from other cars, and safety car periods. A smooth fitted curve gives a much more consistent and trustworthy prediction.

### 3.5 How much a pit stop costs — the pit-loss time

The system calculates the *average* real pit-stop duration recorded for the selected race (restricting to realistic values between 10 and 60 seconds, to exclude obvious data errors). If the selected race doesn't have enough pit-stop records of its own, it falls back to the average for that circuit across all years, and finally to the average across the entire dataset (which comes out to roughly 13 seconds) if nothing more specific is available.

This matters a lot because pit lanes are physically very different in length and speed limit from circuit to circuit — the data shows an average pit stop costing around 21 seconds at the Australian Grand Prix, but around 33 seconds at Imola. Using a single fixed number for every circuit would be unrealistic, so this value — call it $P$ — is always calculated specifically for the race being analyzed.

### 3.6 How long a tyre can safely last — the maximum stint length

For every compound, the system looks at every real stint recorded on that compound (a "stint" being the continuous run on one set of tyres between pit stops) and calculates the *average* of the maximum tyre age reached in each of those stints. In other words: on average, how old did this compound's tyres get before the driver pitted? That average, rounded to a whole number of laps, becomes the maximum durable stint length for that compound — call it $L_c^{\max}$.

As with the other parameters, this prefers the selected race's own data first, falling back to the dataset-wide average if needed. It is also never allowed to come out smaller than what would be mathematically necessary to actually finish the race given however many pit stops are required — if the required number of stints is large and each one must therefore be short, the estimate is nudged upward to the smallest value that still makes finishing the race possible.

### 3.7 Settings the user controls directly

A handful of inputs are not calculated from data at all — they come directly from whoever is running the model, through the web interface:

| What the user can set | What it controls | What happens if left blank |
|---|---|---|
| Minimum pit stops | The fewest stops the strategy is allowed to make | No minimum (0) |
| Maximum pit stops (Model 2 only) | The most stops the strategy is allowed to make — also becomes the pit-stop *target* that Model 2 tries to stay close to | Defaults to whatever the minimum was set to |
| Minimum stint length | The fewest laps any single stint must run once it begins | A sensible data-driven default (the shortest 5% of real stints seen in this race, capped at 5 laps) |
| Maximum sets per compound | How many separate times each compound can be used (teams only bring a limited number of tyre sets to a race) | Zero — meaning that compound cannot be used at all unless the user explicitly allows it |
| Maximum acceptable wear-risk tier per compound (Model 2 only) | An optional hard safety limit — e.g. "never let the Soft tyre get past Moderate wear" | No limit |
| Priority weights (Model 2 only) | How much the user cares about speed vs. avoiding pit stops vs. avoiding tyre wear, as three numbers that must add up to 1 | A default split of 50% speed, 25% fewer pit stops, 25% tyre safety |

Two things are worth understanding about how these are handled: first, if a user enters contradictory values (for example, a maximum pit-stop count lower than the minimum they also set), the system does not silently fix this for them — it stops and explains clearly what is wrong, so the user can correct it themselves rather than unknowingly getting a result based on a guess about what they "really meant." Second, the tyre-set allowance has no automatic default beyond zero: if a user doesn't explicitly say how many sets of a compound are available, the model assumes none are — mirroring the real-world fact that a team only brings a specific, limited number of tyre sets to each race weekend, and cannot use a compound it didn't bring enough of.

---

## 4. Model 1: Finding the Fastest Possible Strategy

Model 1 answers one question only: ignoring every other consideration, what is the single fastest possible way to run this race? It is built as a type of optimization model called a **Mixed-Integer Linear Program**, or MILP — "mixed-integer" because some of its decisions are whole numbers (specifically, yes/no decisions), and "linear" because the objective and all its rules can be written as simple additions and multiplications, which is what lets a solver search through the possibilities efficiently and guarantee it has found the true best answer (not just a good one).

### 4.1 What the model is deciding, lap by lap

For every single lap of the race, and for every tyre compound that's available in this race, the model has a yes/no decision: *is this compound the one fitted to the car on this lap?* Call this decision $x_{l,c}$ — it equals 1 if compound $c$ is active on lap $l$, and 0 otherwise.

The model also has a yes/no decision for every lap: *does a pit stop happen right after this lap?* Call this $p_l$ — it equals 1 if the car pits after lap $l$, 0 otherwise.

Finally, it needs to know exactly when a *new* stint begins — the first lap a given compound is used after not being used the lap before. Call this $s_{l,c}$ — it equals 1 if compound $c$ is freshly fitted at the start of lap $l$.

### 4.2 What the model already knows (the inputs)

Everything calculated above feeds directly into the model:

- $T_{l,c}$ — the predicted lap time for compound $c$ on lap $l$ (Section 3.4).
- $P$ — the pit-stop time cost for this circuit (Section 3.5).
- $L_c^{\max}$ — the maximum safe stint length for compound $c$ (Section 3.6).
- $N$ — the total number of laps in the race.
- The user's minimum pit-stop count, minimum stint length, and tyre-set allowances (Section 3.7).

### 4.3 The goal: minimize total race time

The model's objective is to choose values for every $x_{l,c}$ and $p_l$ that make the total predicted race time as small as possible. Total race time is simply the sum of the predicted lap time actually driven on every lap, plus the time lost to however many pit stops happen:

$$
\min T_{\text{race}} = \sum_{\text{every lap } l} \sum_{\text{every compound } c} T_{l,c} \cdot x_{l,c} \;+\; P \times (\text{total number of pit stops})
$$

### 4.4 The rules the model must obey

A solver cannot just pick whatever makes the objective smallest with no restrictions — that would produce nonsense, like running every lap on the fastest tyre forever with no wear and no pit stops. The following rules keep the model physically and strategically realistic:

**Exactly one tyre at a time.** On any given lap, exactly one compound must be the active one — not zero, not two:
$$
\sum_{\text{every compound } c} x_{l,c} = 1 \qquad \text{for every lap } l
$$

**A pit stop is whatever causes a compound change.** The model defines a pit stop as happening precisely when the active compound on one lap differs from the active compound on the next lap. This is enforced with two rules that together force the pit-stop decision to "turn on" whenever any compound's status flips between consecutive laps:
$$
p_l \ge x_{l,c} - x_{l+1,c} \qquad \text{and} \qquad p_l \ge x_{l+1,c} - x_{l,c}
$$
for every lap $l$ and every compound $c$. (The model is never forced to report a pit stop that didn't happen, because the objective function is trying to *minimize* the number of pit stops in the first place — there's no incentive to claim an extra one.)

**At least the minimum number of pit stops the user required:**
$$
\text{total pit stops} \ge \text{minimum pit stops}
$$

**Correctly identifying when a new stint starts.** A new stint on compound $c$ begins at lap $l$ exactly when that compound is active on lap $l$ but was not active on the lap before. A set of linked rules captures this logic precisely, so that $s_{l,c}$ is forced to 1 only in that exact situation and 0 in every other case.

**No stint shorter than the minimum allowed length.** If a stint starts at lap $l$, the model must keep that same compound active for at least the minimum stint length the user set (unless the race itself ends first):
$$
(\text{active laps on compound } c \text{ from } l \text{ through the required minimum window}) \ge (\text{minimum stint length}) \times s_{l,c}
$$
This only has any effect when a stint truly starts at lap $l$ — otherwise it has no bite.

**No stint longer than that compound's safe maximum.** Symmetrically, if a stint on compound $c$ starts at lap $l$, it cannot run for more laps than that compound's maximum durable stint length $L_c^{\max}$ allows, again only enforced when a stint genuinely starts there.

**Only one new stint can start per lap** — a car cannot begin two different tyre stints simultaneously on the same lap.

**A limited number of tyre sets per compound.** The total number of separate stints run on compound $c$, across the whole race, cannot exceed however many sets of that compound the user said were available — because each stint uses up one physical set of tyres:
$$
\text{total stints on compound } c \le \text{maximum sets of compound } c
$$

**All decisions are yes/no.** Every $x_{l,c}$, $p_l$, and $s_{l,c}$ can only take the value 0 or 1 — there's no such thing as "half" a tyre compound being active.

One rule that might seem necessary but turns out not to be: making sure the stints add up to exactly the full race distance. This happens automatically, because the "exactly one compound active every lap" rule already applies to every single lap of the race from the first to the last — so the stints can never do anything other than cover the whole race exactly once.

### 4.5 What comes out of Model 1

Once solved, Model 1 tells us:

1. Exactly which laps to pit on.
2. Which compound to use in each resulting stint.
3. The minimum possible total race time achievable under these rules — call this number $T^{*}$ ("T-star"). This number becomes important again in Model 2, described next, as the benchmark against which a more balanced strategy is measured.

---

## 5. Model 2: Finding a Balanced, Realistic Strategy

Model 1 answers "what's the fastest possible strategy," full stop. But real race engineers rarely want that in isolation — extra pit stops carry real operational risk (a wheel gun can jam, a wheel nut can be cross-threaded, a release can be unsafe if timed badly), and pushing a tyre well past its comfortable working life risks a sudden, dangerous loss of grip. Model 2 is built to find a strategy that is still fast, but deliberately balances speed against these two other concerns, according to how much the user says they care about each one.

This kind of model is called **Goal Programming**. Instead of a single objective to minimize, it works with several *goals* — target values the user would like to hit — and tries to get as close to all of them as possible at once, where "as close as possible" is itself defined by user-chosen priorities.

### 5.1 It starts from everything Model 1 already has

Model 2 reuses every decision, parameter, and rule from Model 1 exactly as described above — the lap-by-lap compound decisions, the pit-stop detection logic, the minimum stint length rule, the maximum durability rule, and the tyre-set allowance rule. It adds exactly one new rule on top: Model 1 only enforces a *minimum* number of pit stops, but Model 2 also enforces a genuine *maximum*, because the user can set an upper limit on stops for Model 2 specifically:
$$
\text{minimum pit stops} \le \text{total pit stops} \le \text{maximum pit stops}
$$

### 5.2 Three competing goals

Model 2 is given three targets, and it tries to get close to all three simultaneously, weighted by priority:

**Goal 1 — Race time.** The target is $T^{*}$, the true fastest time Model 1 found for this exact race under these exact user settings. Model 2 is never expected to beat this time (it's the mathematically fastest possible), but it's allowed to come in slower than it, by some amount, if that buys a better outcome on the other two goals.

**Goal 2 — Number of pit stops.** The target is simply the maximum pit-stop count the user chose. Because that same number is also enforced as a hard ceiling (Section 5.1), this goal really expresses a *preference* to stay close to that chosen number rather than just technically staying under it.

**Goal 3 — Tyre wear risk.** The target is the lowest possible total wear-risk score achievable for this specific race under these specific settings — how exactly that risk score is calculated is explained fully in the next section. Unlike the first two goals, this target is not something simple to state in one line; it is found by actually solving a smaller version of this same model once, with the sole aim of minimizing wear risk and nothing else, before the real balanced solve happens. This mirrors how the race-time target above is itself the genuine solved optimum from Model 1, rather than a guessed number.

### 5.3 Making the three goals comparable

Race time is measured in seconds, pit-stop count is a small whole number, and the wear-risk score is a unit-less number built from tier weights — three completely different scales. If the model tried to balance "a few seconds of time" against "one fewer pit stop" against "two points of risk score" directly, the weights the user sets wouldn't mean anything sensible, because a "point" of one goal doesn't correspond to a "point" of another.

To fix this, every goal is converted into a *fraction of its own target* before being compared. For each goal, the model introduces two non-negative "deviation" quantities: how much the achieved value overshoots the target, and how much it undershoots it. For example, for the time goal:

$$
\frac{T}{T^{*}} + (\text{undershoot of time goal}) - (\text{overshoot of time goal}) = 1
$$

Here $T$ is the race time this particular candidate strategy actually achieves. If $T$ equals $T^{*}$ exactly, both deviation terms are zero and the equation balances at 1. If $T$ is larger than $T^{*}$ (slower), the overshoot term absorbs that difference as a fraction of $T^{*}$. Since $T^{*}$ is by definition the fastest possible time, $T$ can never legitimately be smaller than it, so the undershoot term for this particular goal always stays at zero in practice — it exists mainly so the equation always has a valid solution.

The exact same idea is applied to the pit-stop goal (actual pit-stop count divided by the target pit-stop count) and the wear-risk goal (actual risk score divided by the target risk score). This way, an "overshoot" of 0.1 means the same thing — "10% worse than the ideal" — no matter which of the three goals it belongs to, which is what makes it meaningful to compare and weight them against each other.

### 5.4 The objective: minimize the weighted overshoot

Model 2's single objective is to minimize a weighted sum of the three overshoot amounts:

$$
\min Z = w_1 \times (\text{time overshoot}) + w_2 \times (\text{pit-stop overshoot}) + w_3 \times (\text{wear-risk overshoot})
$$

where $w_1$, $w_2$, and $w_3$ are the user's priority weights, required to be non-negative and to add up to exactly 1. Only overshooting a target is penalized — a strategy is never punished for *undershooting* a goal (finishing faster than expected, using fewer stops than the ceiling allows, or ending up with less tyre risk than the floor), since all of those are good outcomes, not bad ones.

By default, the weights follow the project's standard convention: 50% weight on time, 25% on pit stops, and 25% on tyre wear — meaning the model is told to care about speed twice as much as it cares about either of the other two factors, by default. These are fully adjustable by the user.

### 5.5 An optional hard safety limit, separate from the weighted goals

In addition to the weighted preference described above, a user can also set an absolute, non-negotiable safety limit for any compound — for example, "never let the Soft compound's tyre age go past the Moderate wear tier, no matter what." This is enforced as a genuine hard rule the solver cannot violate under any circumstance, regardless of how the priority weights are set. It sits underneath Goal 3 as a safety floor, not as a replacement for it — Goal 3 still tries to minimize wear risk as a preference on top of whatever hard limits are in place.

### 5.6 What comes out of Model 2

1. The balanced stint structure and pit-stop laps.
2. The total race time this balanced strategy achieves.
3. The time penalty compared to the pure-speed optimum — e.g. "this strategy costs an extra 1.9 seconds, but saves one pit stop." This is the headline trade-off number shown to the user.
4. How much each of the three goals overshot its target, and the final wear-risk score achieved.
5. A side-by-side comparison against Model 1's result.

---

## 6. How Tyre Wear Risk Is Measured

This part of the project deserves its own explanation, because it's the most involved piece of modeling.

### 6.1 Why a simple label per compound wasn't good enough

An early, simpler idea was to just assign each tyre compound a fixed riskiness label — "Soft is riskier than Hard," full stop. But that misses the real pattern: *any* compound becomes risky once it's been run far enough past its comfortable working life, and a compound run only a few laps is low-risk no matter which one it is. So instead, risk is tracked **lap by lap, based on how old the current tyre actually is at that moment** — a strategy that pushes a tyre deep into its worn-out zone is penalized more, even if that same strategy happens to be slightly faster overall, which makes risk a genuine trade-off the model has to weigh rather than a fixed label glued to a compound name.

### 6.2 Tracking how old each tyre is, lap by lap

To score risk properly, the model needs to know, for every lap and every compound, exactly how many consecutive laps that compound has been in use *in its current stint* — resetting back to the start whenever a new stint begins. Call this the tyre's **age** on that lap.

Because this age must reset conditionally (only when a new stint actually starts, not on every lap), capturing this correctly inside a strictly linear model takes a careful set of paired rules: one set of rules says that if a new stint begins on this lap, the age must be exactly 1; another set says that if the stint is simply continuing from the lap before, the age must be exactly one more than it was the previous lap; and a final rule forces the age to 0 whenever that compound isn't even the one active on this lap. Together, these guarantee the age value the model computes always matches the real, physical tyre age — fresh at the start of every stint, incrementing by one lap at a time, reset at every pit stop. The age is also required to be a whole number, which — beyond being physically correct, since you can't have "2.5 laps" of tyre age — also makes the solver's search noticeably faster.

### 6.3 Four tiers of wear risk

Rather than using a single continuous risk number, tyre wear is split into four tiers — Low, Moderate, High, and Very High — and each tier is given a risk weight: Low costs 0, Moderate costs 1, High costs 2, and Very High costs 3.

Crucially, the age thresholds that separate these tiers are **scaled to each compound's own real durability**, not to one fixed number of laps for every compound. A compound that typically lasts 40 laps and one that typically lasts 20 laps reach the same *relative* level of wear at very different absolute ages — so the boundaries are set at 40%, 70%, and 90% of that specific compound's own maximum durable stint length (calculated in Section 3.6):

- **Low risk:** tyre age is at most 40% of that compound's typical maximum life.
- **Moderate risk:** tyre age is between that point and 70% of typical maximum life.
- **High risk:** tyre age is between that point and 90% of typical maximum life.
- **Very High risk:** tyre age is beyond 90% of typical maximum life.

(This particular 40/70/90 split is a reasonable, physically motivated choice rather than something fitted directly from the data — the project did try to find these boundaries by fitting them to real lap-time-versus-age patterns, but the real-world data turned out to be too affected by other factors — fuel burning off over a race, traffic, and safety car periods — to produce a reliable, trustworthy fit on its own.)

For every lap and every compound, the risk contributed by that lap is simply 3 minus however many of the three tier thresholds the tyre's current age still satisfies — so a tyre firmly in the Low tier contributes 0, while one that has gone past every threshold into Very High contributes the full 3. A lap where that compound isn't even the one in use naturally contributes zero risk, with no special handling needed. The race's total wear-risk score, $R$, is just the sum of every lap's individual risk contribution, across every lap and every compound.

An optional hard safety ceiling (described in Section 5.5) works by simply forcing the tyre's age to never be allowed to cross into a tier higher than whatever the user chose as the limit for that compound.

### 6.4 Finding the best possible wear-risk score

As explained in Section 5.2, Goal 3's target is not an assumed or arbitrary number — it is the genuine lowest wear-risk score achievable for this specific race, under this specific set of constraints (how many pit stops are required, how many tyre sets are available, any safety ceilings already chosen, and so on). The system finds this number by solving a version of the exact same model once beforehand, with its objective temporarily switched to simply "make the wear-risk score as small as possible," ignoring speed and pit-stop count entirely for that one solve. Whatever risk score that produces becomes the real target used afterward in the full, balanced solve.

This target is deliberately *not* fixed at zero, because a perfectly zero-risk strategy is usually physically impossible: once a stint is required to run for at least the minimum stint length the user chose, the tyre is guaranteed to age past the Low tier at some point during that stint. If the target were fixed at an unreachable zero, every possible strategy would show the same unavoidable overshoot, and the model would have no real incentive to try to reduce risk any further than the unavoidable minimum. Using the genuinely achievable best score instead keeps the comparison meaningful — the very best strategy really can hit zero overshoot on this goal, and anything less careful about tyre wear will show up as a real, meaningful penalty.

### 6.5 Double-checking the risk score after solving

After the full balanced strategy has been solved and turned into a concrete, lap-by-lap sequence of tyre compounds, the system independently recalculates the wear-risk score a second time by walking through that final sequence directly — resetting the tracked age to 1 every time the compound changes, and adding up the tier weight for every lap exactly as described above. This acts as a straightforward, independent check that the risk number reported to the user genuinely matches the final strategy, rather than relying solely on the solver's own internal bookkeeping.

---

## 7. How the Solver's Answer Becomes a Strategy

Once a model (either Model 1 or Model 2) has been fully built, it is handed to a solver — by default, a free, fast solver called HiGHS (with another option, CBC, available as a fallback). The solver is given a time limit (20 seconds) so that a user is never left waiting indefinitely; if the time limit is reached before the solver can mathematically *prove* its answer is the absolute best possible one, but it has still found a genuinely workable strategy, that answer is used and clearly labeled as "best found, not proven optimal" rather than being discarded. Only a case where the solver finds no workable answer at all is treated as a real failure.

### 7.1 Reading off which tyre is on which lap

For every lap, the system looks at which compound's yes/no decision came back closest to "yes" and treats that as the compound used on that lap (with lap-time-based tie-breaking in the rare case of an exact tie or missing value).

### 7.2 Cleaning up the raw answer into valid stints

Because solvers work with small numerical tolerances rather than perfectly exact values, the raw lap-by-lap sequence occasionally needs a small cleanup pass to guarantee every resulting stint genuinely respects the minimum and maximum stint-length rules — any stint found to be slightly too long or too short at this stage is automatically split or trimmed so the final reported strategy is always valid.

### 7.3 Building the final report

From the cleaned-up lap sequence, consecutive laps on the same compound are grouped into stints, each with a start lap, an end lap, how many laps long it is, and how much predicted time it takes. The laps immediately before each stint change become the reported pit-stop laps. The total race time is recalculated directly from this final sequence (sum of every lap's predicted time, plus the pit-stop cost multiplied by however many stops there are), and for Model 2, the final weighted objective value is also reported.

---

## 8. Checking Feasibility Before Solving

Rather than simply handing a possibly-impossible combination of user settings straight to the solver and getting back a vague "no solution found," the system runs through a short series of plain, explainable checks *before* solving Model 2, so that if something truly cannot work, the user is told exactly why in terms they can act on:

1. **Is there enough tyre allowance to even make the required number of stops?** The total number of tyre sets the user allowed, added up across every compound, must be at least one more than the minimum number of pit stops required (since every stint uses up one set). If not, the system explains exactly how many sets are available versus how many stints are actually needed.

2. **Does a safety ceiling make a compound impossible to use at all?** If the user has set a wear-risk safety limit for a compound that is stricter than the minimum stint length they've also required, no stint on that compound could ever be run without breaking one rule or the other — this contradiction is caught and explained by name, rather than silently producing a strategy that quietly avoids that compound without saying why.

3. **Can the full race distance even be covered, combining every limit at once?** The system calculates, for every compound, the longest any single stint on it could possibly run (taking the stricter of its physical durability limit and any safety ceiling the user set), multiplies that by however many sets of it are allowed, and adds that up across every compound. If this total is less than the number of laps in the race, there is genuinely no way to finish the race under the combination of limits the user has chosen — and the system reports the exact shortfall, compound by compound, rather than leaving the user guessing which setting to loosen.

---

## 9. How Model 1 and Model 2 Work Together

Every single time Model 2 is run, the system first silently re-solves Model 1 from scratch, using the exact same race, driver, and user settings — this is how it obtains the genuine fastest-possible-time target described in Section 5.2. That number is never cached, assumed, or pulled from history; it is always a fresh, true optimum for the specific situation currently being analyzed.

The overall sequence when a user asks for a balanced (Model 2) strategy is:

1. Solve Model 1 first, to get the true fastest possible race time for these exact settings.
2. Work out the wear-risk tiers for each compound, based on their durability.
3. Run the feasibility checks described above, stopping early with a clear explanation if something can't work.
4. Solve a throwaway version of Model 2 whose only goal is minimizing wear risk, to find the true best-possible risk score.
5. Solve the real, full Model 2 — balancing speed, pit-stop count, and wear risk against each other using the user's chosen weights — using the two solved targets from steps 1 and 4, plus the user's own pit-stop count target.

So the only target in Model 2 that is a direct, unmodified user input is the pit-stop count target; the race-time target and the wear-risk target are both genuinely solved for, each time, specific to the exact race and settings being analyzed.

---

## 10. Checking the Models Against Real Races

To make sure these models produce sensible, trustworthy results — not just mathematically valid but nonsensical ones — the project includes two checking scripts that run both models against real historical races and compare the results to what actually happened.

### 10.1 A broad sanity check across every race

The first script runs both Model 1 and Model 2 across every race in the dataset (or a smaller quick sample), and for each one checks simple, common-sense things: did the solver report success, do the resulting stint lengths add up to exactly the right number of laps for that race, is every stint at least one lap long, and do both models agree on how many laps the race actually has. The results of every single race checked are written out to a spreadsheet file so they can be reviewed afterward, and the check can safely be paused and resumed partway through a long run.

### 10.2 Comparing predictions to what actually happened on track

The second script goes further: for every race that passed the basic sanity check, it finds whoever was the fastest real driver to actually finish that race (excluding anyone who retired early), while being careful to exclude any lap whose recorded time was wildly inflated by a red flag or safety car stoppage rather than reflecting genuine pace. It then re-solves both models for that same race and compares the predicted total race time, and the predicted sequence of tyre compounds and pit stops, against what that real, fastest finishing driver actually did. This produces a report showing, on average, how closely the models' predictions track real race outcomes, and how often the predicted strategy would have been faster than what actually happened on the day — a practical, down-to-earth check of whether the fitted speed and tyre-wear numbers behind the models are realistic, rather than wildly optimistic or pessimistic.

### 10.3 A more detailed, formally planned validation step

The project's design also describes a more detailed, formal comparison — one that would calculate a precise percentage error between predicted and actual race time, and check exactly how well a predicted pit-stop count and stint structure line up with what a real driver did. This more detailed version has not yet been built out in code; the two checking scripts described just above are the methodology's actual, currently working way of validating the models against reality.

---

## 11. A Worked Example With Real Numbers

To make all of this concrete, here is one real result the system produced for the 2018 Abu Dhabi Grand Prix, a 55-lap race:

| | Model 1 (fastest possible) | Model 2 (balanced, limited to 1 pit stop) |
|---|---|---|
| Number of stints | 2 | 2 |
| Number of pit stops | 1 | 1 |
| Pit-stop cost at this circuit | 22.96 seconds | 22.96 seconds |
| Total predicted race time | 5923.39 seconds | 5906.60 seconds |

Interestingly, in this particular example, Model 2 actually came back slightly *faster* than Model 1. That can genuinely happen: Model 1, left completely free, is only required to make *at least* one pit stop and will happily make more stops than that if doing so turns out to be faster overall — whereas in this example, Model 2 was additionally given a hard ceiling of exactly one pit stop. So the two models were answering two subtly different questions here (one with a stop-count ceiling, one without). When both models are given exactly the same minimum and maximum pit-stop limits, Model 2's race time is always at least as slow as Model 1's — it can never beat the genuinely fastest possible time, by definition — and the typical, expected pattern is a small time penalty, something on the order of a couple of extra seconds, in exchange for one fewer pit stop or meaningfully safer tyre usage. That small time penalty, shown clearly to the user, is the headline number the whole balanced-strategy feature is built to produce.

---

## 12. Full List of Symbols Used

| Symbol | What it means |
|---|---|
| $N$ | Total number of laps in the race |
| $l$ | A specific lap number, from 1 up to $N$ |
| $c$ | A specific tyre compound |
| $x_{l,c}$ | 1 if compound $c$ is the active tyre on lap $l$, otherwise 0 |
| $p_l$ | 1 if a pit stop happens right after lap $l$, otherwise 0 |
| $s_{l,c}$ | 1 if a brand-new stint on compound $c$ begins at lap $l$, otherwise 0 |
| $T_{l,c}$ | The predicted lap time for compound $c$ on lap $l$ |
| $P$ | The time cost of one pit stop at this circuit, in seconds |
| $L_c^{\max}$ | The longest a stint on compound $c$ can safely run, in laps |
| $T^{*}$ | The true fastest possible total race time (Model 1's solved result) |
| $R$ | The total tyre wear-risk score of a given strategy |
| $R^{*}$ | The true lowest possible wear-risk score achievable for this race |
| $w_1, w_2, w_3$ | The user's priority weights for speed, pit-stop count, and tyre wear respectively, adding up to 1 |
| $Z$ | Model 2's overall objective value — the weighted total of how much each goal was overshot |

### Where this logic lives in the project's code, for reference

- The combined dataset and the shared loading logic live under the `src/f1_optimizer/common/` folder.
- The bulk of the real parameter calculations described in Section 3 — baseline pace, degradation rate, pit-loss time, durability, and all the feasibility checks — are implemented in `backend/app/services/runner.py`.
- Model 1's mathematical formulation lives in `src/f1_optimizer/scope1/model/milp_model.py`, with its solving logic in `src/f1_optimizer/scope1/solver/milp_solver.py`.
- Model 2's mathematical formulation lives in `src/f1_optimizer/scope2/model/goal_model.py`, with its solving logic in `src/f1_optimizer/scope2/solver/goal_solver.py`.
- The two checking scripts described in Section 10 are `scripts/validate_models.py` and `scripts/compare_to_real.py`.

---

# Run Guide

## 1. Prerequisites

Make sure the following are installed on your machine:

- Python 3.11 or newer
- Node.js 18 or newer
- npm
- Git

## 2. Clone and open the project

```bash
git clone <your-repository-url>
cd F1-Race-Data-Optimization-main
```

## 3. Create the Python environment

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

If the project uses `uv` instead of `pip`, you can also use:

```bash
uv sync
```

## 4. Start the backend

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

API docs will be available at:

- http://localhost:8000/docs
- http://localhost:8000/redoc

## 5. Start the frontend

Open a second terminal and run:

```bash
cd frontend
npm install
npm run dev
```

Then open:

- http://localhost:5173/

## 6. Useful project commands

### Run backend tests

```bash
source .venv/bin/activate
pytest -q
```

### Run frontend build check

```bash
cd frontend
npm run build
```

## 7. Project structure summary

- `backend/` - FastAPI application and API routes
- `src/f1_optimizer/` - optimization models and solver logic
- `data/` - processed and raw race datasets
- `frontend/` - React + Vite dashboard
- `tests/` - validation and regression tests
- `docs/` - project architecture and analysis documents

## 8. Notes

- Do not commit local environment folders such as `.venv/`
- Do not commit generated caches or temporary artifacts
- Do not commit PDF or presentation files unless specifically required by the project brief
</content>
