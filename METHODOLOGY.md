# Methodology: F1 Race Strategy & Performance Optimization

**Course:** Operations Research — Course Project (Team B13: Pranesh L, Kathir Velan M, Sasi Kumar P, Jeiesh S)
**Purpose of this document:** a complete, self-contained walkthrough of every step, formula, and constraint in the project — from raw data to the final optimized race strategy — written so that someone with no prior exposure to the codebase can learn the full method and reproduce it.

This document describes the system **as actually implemented** (`backend/app/services/runner.py`, `src/f1_optimizer/scope1/`, `src/f1_optimizer/scope2/`), not just the idealized textbook formulation. Where the real implementation refines or extends the original slide-deck formulation, both are shown, with the reason for the refinement explained.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Data Pipeline](#2-data-pipeline)
3. [Parameter Estimation from Data](#3-parameter-estimation-from-data)
4. [Model 1 — MILP: Fastest Possible Strategy](#4-model-1--milp-fastest-possible-strategy)
5. [Model 2 — Goal Programming: Balanced Strategy](#5-model-2--goal-programming-balanced-strategy)
6. [Degradation-Risk Scoring (Goal 3 in depth)](#6-degradation-risk-scoring-goal-3-in-depth)
7. [Solving and Extracting a Strategy](#7-solving-and-extracting-a-strategy)
8. [Feasibility Checks Before Solving](#8-feasibility-checks-before-solving)
9. [Integration: Linking Model 1 and Model 2](#9-integration-linking-model-1-and-model-2)
10. [Validation Against Real Race Results](#10-validation-against-real-race-results)
11. [Worked Numerical Example](#11-worked-numerical-example)
12. [Glossary of Symbols](#12-glossary-of-symbols)

---

## 1. Problem Statement

In a Formula 1 Grand Prix:

- The race covers a fixed number of laps $N$ (typically 50–70, varies by circuit).
- Regulations require at least one pit stop, using at least two different dry tyre compounds (in a dry race).
- Three dry compounds are nominally available: **Soft (S)**, **Medium (M)**, **Hard (H)** — though the exact labels present differ by era (2018 used HYPERSOFT/ULTRASOFT/SUPERSOFT/SOFT/MEDIUM/HARD; 2019+ consolidated to SOFT/MEDIUM/HARD; wet races add INTERMEDIATE/WET).
- Softer compounds are faster per lap but degrade (lose pace) faster with tyre age; harder compounds are slower but last longer.
- Every pit stop costs real time: the car must enter the pit lane, stop, have tyres changed, and re-join — a net loss of roughly 13–30 seconds of track time depending on the circuit's pit lane geometry.

**The decision a race engineer must make:**
1. How many pit stops to make.
2. On which exact laps to pit.
3. Which compound to fit for each resulting stint.
4. How to trade pure lap-time speed against the operational risk of pitting and the risk of running a tyre too far into its wear life.

Two optimization models are built to answer this:

| Model | Type | Answers |
|---|---|---|
| **Model 1 (Scope 1)** | Mixed-Integer Linear Program (MILP) | "What is the single fastest possible strategy?" |
| **Model 2 (Scope 2)** | Goal Programming (weighted deviations) | "What is the best *balanced* strategy, trading a little time for fewer stops and safer tyre usage?" |

Both models are built and solved with [PuLP](https://coin-or.github.io/pulp/) (HiGHS solver by default, CBC as a fallback), using **real historical F1 timing data** to derive every parameter — nothing is hand-assumed.

---

## 2. Data Pipeline

### 2.1 Raw sources

```
data/raw/kaggle/   — Historical F1 database (1950–2024): races, results, pit_stops,
                      lap_times, drivers, constructors, etc. (Kaggle "Formula 1 World
                      Championship" dataset)
data/raw/fastf1/   — Per-lap telemetry extracts (2018–2024) via the FastF1 Python
                      library: Compound, TyreLife (tyre age in laps), Stint number,
                      Position, per the official F1 timing feed.
```

### 2.2 Combined dataset

`scripts/build_dataset.py` joins the two sources into a single master file:

```
data/processed/combined_dataset.csv   — 161,443 rows, one row per (driver, lap),
                                         seasons 2018–2024.
```

**Join key:** `[Year, Race, Driver, Lap]`

**Schema:**

| Column | Type | Meaning |
|---|---|---|
| `raceId` | int | Kaggle race identifier |
| `Year` | int | Season |
| `Race` | string | Grand Prix name |
| `Driver` | string | 3-letter driver code |
| `Team` | string | Constructor |
| `Lap` | int | Lap number |
| `LapTime` | string | `M:SS.sss` format |
| `Position` | int | Track position at end of lap |
| `Compound` | string | Tyre compound label |
| `TyreLife` | float | Tyre age in laps (resets to 1 at each pit stop) |
| `Stint` | float | Stint index (increments at each pit stop) |
| `pit_duration` | float | Pit-stop duration in seconds, `NaN` if no stop that lap |

This file is treated as a **fixed, pre-validated artifact** — it is never rebuilt or modified during normal runs. All access goes through one interface: `DatasetLoader` (`src/f1_optimizer/common/data/dataset_loader.py`), which:
- caches the CSV in memory,
- coerces `LapTime` strings and `Lap`/`pit_duration` numerics,
- exposes `get_race_dataframe(year, race_name, driver_code)` to pull exactly the rows needed for one optimization run.

### 2.3 Lap-time string parsing

`src/f1_optimizer/common/utils/time_utils.py`:

$$
\text{seconds} = \begin{cases} 60 \cdot \text{minutes} + \text{seconds} & \text{if "M:SS.sss" format} \\ \text{seconds} & \text{if plain seconds} \end{cases}
$$

Implemented with a regex `(?:(\d+):)?(\d+(?:\.\d+)?)` so both `"1:28.176"` and `"88.176"` parse correctly. This is the single utility used everywhere a lap time needs to become a float.

---

## 3. Parameter Estimation from Data

Every mathematical parameter fed into the two models is **derived from real data**, computed in `BackendOptimizationRunner` (`backend/app/services/runner.py`). This section documents exactly how.

### 3.1 Available compounds, $C$

```
_get_available_compounds(race_df)
```
Takes the literal set of `Compound` values present in that race's rows (uppercased), removes junk values (`NAN`, `UNKNOWN`, `NONE`, `""`), and orders them softest → hardest using a fixed Pirelli softness ranking:

$$
\text{HYPERSOFT} \prec \text{ULTRASOFT} \prec \text{SUPERSOFT} \prec \text{SOFT} \prec \text{MEDIUM} \prec \text{HARD} \prec \text{INTERMEDIATE} \prec \text{WET}
$$

This means $C$ is **race-specific** (a 2018 race might have 3 compounds from `{HYPERSOFT, SUPERSOFT, SOFT}`; a 2023 race uses `{SOFT, MEDIUM, HARD}`), rather than a hardcoded fixed set. If nothing usable is found, it defaults to `["SOFT", "MEDIUM", "HARD"]`.

### 3.2 Baseline pace per compound, $\text{Base}_c$

```
_get_compound_base_pace(compounds, race_df)
```
Mean real lap time (in seconds) for each compound, with a three-level fallback:

$$
\text{Base}_c = \begin{cases}
\text{mean lap time for } c \text{ in this specific race} & \text{if that race has laps on } c \\
\text{mean lap time for } c \text{ across the whole 2018–2024 dataset} & \text{if not, but other races do} \\
\text{mean lap time across all compounds, dataset-wide} & \text{as a last resort}
\end{cases}
$$

Why race-specific first: lap time is dominated by circuit characteristics (e.g. Monaco ≈ 82s vs. a global Soft average ≈ 97s pooled across every circuit). Using the race's own laps keeps the baseline physically meaningful for that circuit.

### 3.3 Degradation rate per compound, $\alpha_c$

```
_get_compound_degradation_rate(compounds, race_df)  →  _fit_degradation_rates(df)
```

For each compound, an ordinary least-squares **linear regression** of lap time against tyre age is fit:

$$
\text{LapTime} = \text{Base}_c + \alpha_c \cdot \text{TyreAge}
$$

Implemented as a slope using covariance/variance (equivalent to simple linear regression):

$$
\alpha_c = \frac{\operatorname{Cov}(\text{TyreLife}, \text{LapSeconds})}{\operatorname{Var}(\text{TyreLife})}
$$

**Rules applied:**
- Needs at least 5 rows and at least 2 distinct tyre-age values for that compound, otherwise that compound is skipped (falls through to the dataset-wide fit, then to $\alpha_c = 0$).
- The slope is **floored at 0**: $\alpha_c = \max(\alpha_c, 0)$. A tyre is never modeled as getting *faster* with age — a negative raw slope only appears when fuel burn-off or traffic dominates the signal, which is a confound, not real degradation.
- Same race-specific → dataset-wide → 0.0 fallback order as baseline pace.

(`src/f1_optimizer/common/tyre/degradation_model.py` contains an equivalent, more general `TyreDegradationModel.fit_compound_degradation` using `numpy.polyfit` across every lap of a given compound — same floored-OLS idea — kept as the common/reusable version of this fit.)

### 3.4 Predicted lap time, $T_{l,c}$

```
_build_predicted_lap_times(df, compounds, total_laps)
```

$$
T_{l,c} = \text{Base}_c + \alpha_c \cdot l \qquad \forall\, l \in \{1, \dots, N\},\ c \in C
$$

Note this uses the **absolute lap number** $l$ as the age proxy inside the lookup table (not stint-relative age) — the stint-relative tyre age is reconstructed later by the model itself (see §4 and §6) when it needs to know how long a tyre has actually been on the car within its *current* stint. The raw table $T_{l,c}$ simply answers "how fast would compound $c$ be if it had been on since lap 1" for every lap; the model's own stint-tracking logic is what correctly resets the effective age at each pit stop.

Why the fitted curve and not raw per-lap averages: raw per-lap data is noisy (fuel load changes every lap, traffic, Safety Car laps), so a smooth fitted line is used everywhere for consistency instead.

### 3.5 Pit-stop time loss, $P$

```
_get_pit_loss_seconds(year, race_name)
```

Mean real `pit_duration` (seconds), filtered to a sane physical range $[10, 60]$ seconds to exclude data errors, with a three-level fallback identical in spirit to §3.2:

$$
P = \begin{cases}
\text{mean pit\_duration for this exact (year, race)} \\
\text{mean pit\_duration for this circuit, any year} \\
\text{mean pit\_duration across the whole dataset (fallback } \approx 13\text{s)}
\end{cases}
$$

This matters because pit-lane length varies hugely by circuit — the dataset shows ≈20.6s at Australia vs. ≈32.7s at Imola. (This also resolves the slide-deck's own internal ambiguity between "$P \approx 13$s" on the MILP slide and "$\approx 20$s" on the background slide — $P$ is computed per race rather than fixed.)

### 3.6 Maximum durable stint length per compound, $L_c^{\max}$

```
_get_max_stint_durability(compounds, race_df, total_laps, max_stints)
```

Computed as the **mean of the maximum `TyreLife` reached per real stint**, per compound (`TyreStatisticsCalculator.calculate_mean_max_stint_life`):

$$
L_c^{\max} = \max\!\left(1, \ \operatorname{round}\!\big(\operatorname{mean}_{\text{stints of } c}(\max \text{TyreLife in that stint})\big)\right)
$$

Same race-specific → dataset-wide fallback pattern, and additionally floored so the chosen number of stints can actually cover the race:

$$
L_c^{\max} \ge \left\lceil \frac{N}{\text{max\_stints}} \right\rceil, \qquad \text{max\_stints} = \text{min\_pit\_stops} + 1
$$

(so a durability estimate that's too small to ever complete the race, given how many stints the user requires, is automatically raised to the minimum geometrically necessary.)

### 3.7 User-configurable inputs

These are **not fit from data** — they come directly from the user's request, validated/clamped by `_resolve_strategy_constraints`, `_resolve_max_pit_stops`, `_resolve_max_sets_per_compound`, `_resolve_max_risk_tier_per_compound`:

| Parameter | Meaning | Default when blank |
|---|---|---|
| `min_pit_stops` | Hard floor on number of stops | 0 |
| `max_pit_stops` (Model 2 only) | Hard ceiling on number of stops; also sets Goal 2's target $P^*$ | `min_pit_stops` itself |
| `min_stint_length` | Minimum laps any stint must run once started | data-driven: the race's real 5th-percentile stint length, capped at 5 |
| `max_sets_per_compound` | How many separate stints (tyre sets) of each compound are allowed | 0 per compound (i.e. unusable unless specified) |
| `max_risk_tier_per_compound` (Model 2 only) | Optional hard ceiling on degradation-risk tier per compound | none (no ceiling) |
| `weights` $(w_1, w_2, w_3)$ (Model 2 only) | Relative priority across the three goals | $0.50/0.25/0.25$ |

Two design decisions worth calling out:
- There is **no silent clamping** of contradictory inputs (e.g. `max_pit_stops < min_pit_stops`) — the system raises a clear, actionable error instead of guessing what the user meant.
- `max_sets_per_compound` has **no auto-default** besides 0 — if the user doesn't explicitly allocate tyre sets to a compound, that compound is unusable. This models the real constraint that teams bring a finite, pre-declared allocation of tyres to a race weekend.

---

## 4. Model 1 — MILP: Fastest Possible Strategy

**File:** `src/f1_optimizer/scope1/model/milp_model.py`
**Goal:** find the single fastest theoretical strategy — pit-stop laps, compound per stint — subject to physical/regulatory constraints.

### 4.1 Sets

- $l \in \{1, 2, \dots, N\}$ — race laps.
- $c \in C$ — tyre compounds present in this race's data (§3.1).

### 4.2 Decision variables

| Variable | Domain | Meaning |
|---|---|---|
| $x_{l,c}$ | $\{0,1\}$ | 1 if compound $c$ is the active tyre on lap $l$ |
| $p_l$ | $\{0,1\}$ | 1 if a pit stop occurs between lap $l$ and lap $l+1$ |
| $s_{l,c}$ | $\{0,1\}$ | 1 if a **new stint** on compound $c$ starts on lap $l$ (i.e. compound $c$ is active on lap $l$ but was not active on lap $l-1$) |

### 4.3 Parameters

| Symbol | Meaning | Source |
|---|---|---|
| $T_{l,c}$ | Predicted lap time | §3.4 |
| $P$ | Pit-stop time loss | §3.5 |
| $L_c^{\max}$ | Max durable stint length | §3.6 |
| $N$ | Total race laps | race data |
| $\text{min\_pit\_stops}$ | Floor on stop count | §3.7 |
| $\text{min\_stint\_length}$ | Floor on any stint's length | §3.7 |
| $\text{max\_sets}_c$ | Ceiling on number of stints of compound $c$ | §3.7 |

### 4.4 Objective function

$$
\min T_{\text{race}} = \sum_{l=1}^{N} \sum_{c \in C} T_{l,c}\, x_{l,c} \;+\; P \sum_{l=1}^{N-1} p_l
$$

Total predicted race time = sum of the lap time actually driven on each lap, plus the time lost to however many pit stops are made.

### 4.5 Constraints

**(a) Compound exclusivity** — exactly one compound is on the car every lap:
$$
\sum_{c \in C} x_{l,c} = 1 \qquad \forall\, l \in \{1,\dots,N\}
$$

**(b) Pit-stop detection (linking $p_l$ to compound changes)** — a pit stop is logically *defined* as any lap-to-lap compound change:
$$
p_l \ge x_{l,c} - x_{l+1,c} \qquad \text{and} \qquad p_l \ge x_{l+1,c} - x_{l,c} \qquad \forall\, l \in \{1,\dots,N-1\},\ \forall c \in C
$$
These two inequalities together force $p_l = 1$ whenever *any* compound's indicator differs between consecutive laps, and allow $p_l = 0$ only when every compound's indicator is unchanged. ($p_l$ is not separately forced to 0 when nothing changes, but the minimization objective does that automatically since $P>0$ and $p_l$ only appears as a cost.)

**(c) Minimum pit-stop count:**
$$
\sum_{l=1}^{N-1} p_l \ \ge\ \text{min\_pit\_stops}
$$

**(d) Stint bookkeeping — defining $s_{l,c}$:**
$$
s_{l,c} \le x_{l,c} \qquad \forall l,c
$$
$$
s_{1,c} = x_{1,c}
$$
$$
s_{l,c} \le 1 - x_{l-1,c}, \qquad s_{l,c} \ge x_{l,c} - x_{l-1,c} \qquad \forall l>1,\ \forall c
$$
Together these force $s_{l,c}=1$ exactly when compound $c$ is newly activated on lap $l$ (active now, inactive the lap before), and $0$ otherwise.

**(e) Minimum stint length** — any stint that starts must run for at least `min_stint_length` laps (unless the race ends first):
$$
\sum_{l'=l}^{\min(N,\, l+\text{min\_stint\_length}-1)} x_{l',c} \ \ge\ \text{min\_stint\_length} \cdot s_{l,c} \qquad \forall l,c
$$
If $s_{l,c}=1$ (a stint truly starts here), the left side must count at least `min_stint_length` consecutive active laps on $c$ starting at $l$; if $s_{l,c}=0$ the constraint is vacuous.

**(f) Tyre durability** — any stint that starts cannot run longer than that compound's durable limit $L_c^{\max}$, enforced with a Big-M relaxation that only binds when the stint truly started at $l$:
$$
\sum_{l'=l}^{\min(N,\, l+L_c^{\max})} x_{l',c} \ \le\ L_c^{\max} + (N+1)\,(1 - s_{l,c}) \qquad \forall l,c
$$
When $s_{l,c}=1$, this caps the window's active-lap count at $L_c^{\max}$. When $s_{l,c}=0$, the Big-M term $(N+1)$ makes the constraint non-binding.

**(g) At most one stint starts per lap:**
$$
\sum_{c \in C} s_{l,c} \ \le\ 1 \qquad \forall l
$$

**(h) Tyre-set allocation ceiling** — the number of separate stints run on compound $c$ cannot exceed the sets allocated to it (this is the real-world cap on how many times a compound can be used, since each stint consumes one physical tyre set):
$$
\sum_{l=1}^{N} s_{l,c} \ \le\ \text{max\_sets}_c \qquad \forall c \in C
$$

**(i) Binary integrality:**
$$
x_{l,c},\ p_l,\ s_{l,c} \ \in\ \{0,1\}
$$

Note: **full race distance coverage** ($\sum_i \text{stint}_i = N$) is not a separate constraint — it falls out automatically from (a) (exactly one compound active every lap, for all $N$ laps).

### 4.6 Output

The optimal $x_{l,c}^*$, $p_l^*$ give:
1. Optimal pit-stop laps.
2. Compound fitted in each stint.
3. Minimum predicted total race time $T^* = T_{\text{race}}^*$.

This $T^*$ is the number later fed into Model 2 as the "fastest achievable" benchmark (§9).

---

## 5. Model 2 — Goal Programming: Balanced Strategy

**File:** `src/f1_optimizer/scope2/model/goal_model.py`
**Motivation:** real teams rarely optimize on raw speed alone. Extra pit stops carry operational risk (a stuck wheel gun, a cross-threaded nut, an unsafe release); pushing a tyre too far risks a sudden loss of grip or a structural failure. Model 2 finds a **balanced** strategy that trades a controlled, small amount of race time for fewer stops and lower tyre-degradation risk, according to team-assigned priorities.

### 5.1 All of Model 1's variables and constraints, plus:

Model 2 reuses every decision variable and constraint from §4.2–§4.5 ($x_{l,c}$, $p_l$, $s_{l,c}$, constraints (a)–(i)), **with one addition**: a genuine hard **ceiling** on pit stops (Model 1 only has a floor):
$$
\text{min\_pit\_stops} \ \le\ \sum_{l=1}^{N-1} p_l \ \le\ \text{max\_pit\_stops}
$$

Then it adds the goal-programming machinery below.

### 5.2 Additional decision variables

| Variable | Domain | Meaning |
|---|---|---|
| $d_1^+, d_1^-$ | $\ge 0$ | Over-/under-achievement deviation, Goal 1 (time) |
| $d_2^+, d_2^-$ | $\ge 0$ | Over-/under-achievement deviation, Goal 2 (pit stops) |
| $d_3^+, d_3^-$ | $\ge 0$ | Over-/under-achievement deviation, Goal 3 (degradation risk) |
| $\text{age}_{l,c}$ | Integer $\ge 0$ | Consecutive laps compound $c$ has run, counting lap $l$ itself (see §6) |
| $\ell_{l,c,k}$ for $k\in\{1,2,3\}$ | $\{0,1\}$ | 1 iff $\text{age}_{l,c} \le$ tier-$k$ threshold (see §6) |

### 5.3 The three goals

Each goal equation is **normalized by its own target** so the three deviations $d_1^+, d_2^+, d_3^+$ are comparable *fractional* quantities (0 = exactly on target) rather than raw units of wildly different scale (seconds vs. a stop count vs. a unitless risk score). Without normalization, the weights $w_1, w_2, w_3$ could not meaningfully trade off against each other.

**Goal 1 — Race time.** Target $T^*$ = Model 1's own solved optimum (§4.6):
$$
\frac{T}{T^*} + d_1^- - d_1^+ = 1
$$
where $T = \sum_{l,c} T_{l,c}\,x_{l,c} + P\sum_l p_l$ (identical expression to Model 1's objective). Since $T^*$ is the *unconstrained* minimum, in practice $T \ge T^*$ always, so $d_1^-$ stays 0 and $d_1^+$ is the fractional time penalty this balanced strategy accepts.

**Goal 2 — Pit-stop count.** Target $P^*$ = the user's `max_pit_stops` input, taken directly:
$$
\frac{P_{\text{stops}}}{P^*} + d_2^- - d_2^+ = 1
$$
where $P_{\text{stops}} = \sum_l p_l$. Because `max_pit_stops` is *also* enforced as a genuine hard ceiling (§5.1), $d_2^+$ in practice only measures how far the chosen strategy sits below that ceiling when it's being used as a *preferred* value, not just a maximum.

**Goal 3 — Degradation risk.** Target $R^*$ = the true minimum risk score achievable under this race's actual constraints (computed by a dedicated solver pass — see §6.4):
$$
\frac{R}{R^*} + d_3^- - d_3^+ = 1
$$
where $R$ is the strategy's total degradation-risk score (defined fully in §6).

If a target is $0$ (edge case), the corresponding equation falls back to its **un-normalized** raw-unit form instead of dividing by zero.

### 5.4 Objective function

$$
\min Z = w_1 d_1^+ + w_2 d_2^+ + w_3 d_3^+
$$
subject to
$$
w_1 + w_2 + w_3 = 1, \qquad w_1, w_2, w_3 \ge 0
$$

Only the **overshoot** terms are penalized. Undershooting a target — finishing faster than $T^*$ (impossible, since $T^*$ is the true minimum), making fewer stops than $P^*$, or achieving lower risk than $R^*$ — is never penalized; $d_k^-$ exists purely so each goal equation can still balance to 1 in that case.

**Default weights** (PPT Slide 14 convention, enforced to sum to 1 by `GoalWeights`):
$$
w_1 = 0.50 \ (\text{time}), \quad w_2 = 0.25 \ (\text{pit stops}), \quad w_3 = 0.25 \ (\text{tyre preservation})
$$
User-adjustable through the UI.

### 5.5 Optional hard safety ceiling (separate from Goal 3)

A user can additionally set `max_risk_tier_per_compound` — e.g. "never let SOFT exceed the Moderate tier." This is enforced as an **absolute hard constraint** (detailed in §6.3), independent of the weights — it is a safety bound layered *underneath* Goal 3's soft preference, not a replacement for it.

### 5.6 Output

1. Balanced stint structure and pit-stop laps.
2. Achieved race time $T_{\text{balanced}}$.
3. Trade-off delta $\Delta T = T_{\text{balanced}} - T^*$ (e.g. "+1.9s to save one pit stop").
4. Achieved deviations $d_1^+, d_2^+, d_3^+$ and the realized risk score $R$.
5. A side-by-side comparison against Model 1.

---

## 6. Degradation-Risk Scoring (Goal 3 in depth)

This is the most intricate part of the model, so it gets its own section.

### 6.1 Why not a flat index?

An early design used a static per-compound risk label. The implemented version instead makes risk a genuine **per-lap, age-aware** score: a strategy that runs a compound deep into its high-wear zone costs more here, even if it happens to be marginally faster — so risk is a real trade-off the optimizer weighs, not a fixed label attached to a compound name.

### 6.2 Tracking tyre age inside the MILP ($\text{age}_{l,c}$)

Tyre age must reset to 1 every time a new stint starts and increment by 1 every other active lap — this is inherently a *conditional* reset, which is non-linear unless encoded carefully with Big-M logic. For each compound $c$, let $\text{big\_m}_c = L_c^{\max} + 1$ (scoped **per compound**, not to the full race distance $N$ — this keeps the LP relaxation much tighter, which matters for solver speed given how many binary variables this model already has):

$$
\text{age}_{l,c} \ \le\ \text{big\_m}_c \cdot x_{l,c} \qquad \forall l,c
$$
(age is 0 whenever the compound isn't active that lap.)

For $l=1$:
$$
\text{age}_{1,c} = x_{1,c}
$$

For $l>1$, let $a' = \text{age}_{l-1,c}$ (previous lap's age):
$$
\text{age}_{l,c} \ \le\ a' + 1 + \text{big\_m}_c\,(1-x_{l,c})
$$
$$
\text{age}_{l,c} \ \ge\ a' + 1 - \text{big\_m}_c\,(1-x_{l,c}) - \text{big\_m}_c\, s_{l,c}
$$
$$
\text{age}_{l,c} \ \le\ 1 + \text{big\_m}_c\,(1-s_{l,c})
$$
$$
\text{age}_{l,c} \ \ge\ 1 - \text{big\_m}_c\,(1-s_{l,c})
$$

Read together: if $x_{l,c}=0$, age is forced to 0 by the first constraint. If $x_{l,c}=1$ and $s_{l,c}=1$ (a new stint just started), the last two constraints pin $\text{age}_{l,c}=1$. If $x_{l,c}=1$ and $s_{l,c}=0$ (continuing an existing stint), the middle two constraints pin $\text{age}_{l,c} = a'+1$. `age` is declared as an **Integer** variable (not continuous) — tyre age is inherently a whole number of laps, and declaring it integer tightens the solver's branch-and-bound search versus a continuous relaxation.

### 6.3 Risk tiers

Tyre wear is bucketed into 4 tiers, **scaled to each compound's own real durability** $L_c^{\max}$ rather than a fixed absolute age cutoff — a compound that durably lasts 40 laps and one that lasts 20 reach the same *relative* wear state at different absolute ages.

Tier thresholds (`_get_degradation_risk_tiers`):
$$
t_1 = \max(1, \operatorname{round}(0.40\, L_c^{\max})), \quad t_2 = \max(t_1+1, \operatorname{round}(0.70\, L_c^{\max})), \quad t_3 = \max(t_2+1, \operatorname{round}(0.90\, L_c^{\max}))
$$

| Tier | Age range | Risk weight | Meaning |
|---|---|---|---|
| 0 — Low | $\text{age} \le t_1$ | 0 | Fresh tyre |
| 1 — Moderate | $t_1 < \text{age} \le t_2$ | 1 | Normal wear |
| 2 — High | $t_2 < \text{age} \le t_3$ | 2 | Pushing the limit |
| 3 — Very high | $\text{age} > t_3$ | 3 | Beyond recommended life |

(The 40%/70%/90% split is a physically reasonable choice, not a data fit — fitting these boundaries directly from lap-time-vs-age data was attempted but showed no usable monotonic signal in this dataset, confounded by fuel burn-off, traffic, and Safety Car periods.)

Encoded with binary indicators $\ell_{l,c,k}$ ("is age $\le t_k$?"), using a per-compound Big-M equal to $L_c^{\max}$:
$$
\text{age}_{l,c} \ \le\ t_1 + L_c^{\max}(1-\ell_{l,c,1}), \quad
\text{age}_{l,c} \ \le\ t_2 + L_c^{\max}(1-\ell_{l,c,2}), \quad
\text{age}_{l,c} \ \le\ t_3 + L_c^{\max}(1-\ell_{l,c,3})
$$

These are naturally nested ($\text{age}\le t_1 \Rightarrow \text{age}\le t_2 \Rightarrow \text{age}\le t_3$, since $t_1<t_2<t_3$), so $\ell_{l,c,1} \le \ell_{l,c,2} \le \ell_{l,c,3}$ holds automatically — no explicit ordering constraint is needed.

**Per-lap risk penalty:**
$$
\text{risk}_{l,c} = 3 - \ell_{l,c,1} - \ell_{l,c,2} - \ell_{l,c,3}
$$
(all three tier-checks true → tier 0 → penalty 0; none true → tier 3 → penalty 3.) Since this is minimized, the solver is naturally driven to push age down / $\ell$ up wherever possible; a lap where the compound isn't active ($x=0$, age$=0$) trivially satisfies all three tier checks, so it contributes 0 risk with no special-casing needed.

**Total risk score:**
$$
R = \sum_{l=1}^{N} \sum_{c \in C} \left(3 - \ell_{l,c,1} - \ell_{l,c,2} - \ell_{l,c,3}\right)
$$

**Optional hard safety ceiling** (`max_risk_tier_per_compound`, separate from the Goal 3 soft preference):

| Chosen ceiling | Enforcement |
|---|---|
| Max tier 0 (Low) | $\ell_{l,c,1} = 1 \ \forall l$ — age may never exceed $t_1$ |
| Max tier 1 (Moderate) | $\ell_{l,c,2} = 1 \ \forall l$ — age may never exceed $t_2$ |
| Max tier 2 (High) | $\ell_{l,c,3} = 1 \ \forall l$ — age may never exceed $t_3$ |
| Max tier 3 (Very high) | No restriction (already the ceiling) |

### 6.4 Computing $R^*$ (Goal 3's target)

$R^*$ is **not** fixed at 0 — a tyre cannot physically stay in the lowest risk tier for an entire stint once it must run at least `min_stint_length` laps, so an unreachable $R^*=0$ would leave every strategy with the same unavoidable $d_3^+$ floor and give the optimizer no real pressure to minimize risk further.

Instead, $R^*$ is found by actually **solving the model once with its objective swapped** to `minimize R` alone (`Scope2GoalModel(..., minimize_risk_only=True)`), keeping every other constraint identical (stint lengths, durability, tyre-set limits, min/max pit stops, and any `max_risk_tier_per_compound` ceilings already in force). This mirrors exactly how $T^*$ is already Model 1's own solved optimum rather than an assumed value — both "ideal" targets in Model 2 are genuinely *solved for*, not guessed.

### 6.5 Recomputing risk after solving (verification)

After the real balanced solve finishes and a concrete lap-by-lap compound sequence is extracted, `Scope2GoalSolver._compute_risk_score` independently recomputes $R$ by walking the final sequence lap-by-lap, resetting age to 1 at each compound change and summing tier weights — a direct, non-MILP cross-check of the value the age/tier constraints produced.

---

## 7. Solving and Extracting a Strategy

**Solver:** [PuLP](https://coin-or.github.io/pulp/), defaulting to the **HiGHS** backend (free, and faster in practice than CBC on this project's models — especially the risk-tier formulation, which adds a lot of binary variables), with `PULP_CBC_CMD` as the alternative. A time limit (20s by default) is applied: a very good but not provably optimal solution returned within a bounded time is more useful to a user than an indefinite wait for a proof of optimality. A solve that hits the time limit but still has a feasible integer solution reports status `"Not Solved"` and is accepted (reported to the user as *"Best found (time limit reached)"*); only a genuinely infeasible model is rejected.

### 7.1 Extracting the lap-by-lap compound sequence

For each lap, the compound whose $x_{l,c}$ value is highest is selected (`_extract_lap_compounds`); ties/missing values fall back to whichever compound has the lowest predicted lap time at that lap.

### 7.2 Normalizing into valid stints

`_normalize_to_valid_stints` is a guardrail pass: it re-chunks any raw block of same-compound laps that violates the durability ceiling or minimum-stint-length floor (which can happen at the solver's numeric tolerance boundaries), splitting or capping blocks so every reported stint is truly within $[\text{min\_stint\_length}, L_c^{\max}]$.

### 7.3 Building the stint list and final metrics

From the normalized sequence, consecutive same-compound runs become `StintPlan` entries (`stint_number`, `compound`, `start_lap`, `end_lap`, `stint_length`, `predicted_stint_time`). Pit-stop laps are the laps immediately preceding each stint boundary. Final reported totals:
$$
T_{\text{total}} = \sum_{l,c} T_{l,c}\, x_{l,c}^{*} + P \cdot |\{\text{pit laps}\}|
$$
and, for Model 2, the objective value
$$
Z^{*} = w_1 d_1^{+*} + w_2 d_2^{+*} + w_3 d_3^{+*}
$$

---

## 8. Feasibility Checks Before Solving

Rather than letting an infeasible model silently fail or time out inside the solver, `BackendOptimizationRunner.run_scope2` runs a chain of **explicit, human-readable feasibility checks** first:

1. **Tyre-set sufficiency:** total allocated sets across all compounds must be $\ge \text{min\_pit\_stops}+1$ (the minimum number of stints any valid strategy needs). If not, rejected with the exact shortfall shown.
2. **Risk-ceiling vs. minimum stint length:** if a requested `max_risk_tier_per_compound` ceiling's age threshold is smaller than `min_stint_length`, no valid stint on that compound could ever stay within the ceiling — rejected with the specific compound and numbers named.
3. **Total coverage under combined constraints:** the maximum laps any compound can contribute is $\min(\text{tier cap if any}, L_c^{\max}) \times \text{max\_sets}_c$; summed across all compounds, this must be $\ge N$. If the risk ceilings and tyre-set limits together can't physically cover the race distance, this is caught and reported with a full per-compound breakdown — *before* ever invoking the solver.

This design choice (checked explicitly in `backend/app/services/runner.py` rather than relying on PuLP's own infeasibility message) is what turns an opaque "Infeasible" solver status into an actionable message telling the user exactly which input to relax.

---

## 9. Integration: Linking Model 1 and Model 2

```
run_scope2(request)
  1. Calls build_strategy_preview(...) → solves Model 1 → scope1_target = T*
  2. Derives risk_tiers from max_stint_durability (§6.3)
  3. Runs the feasibility chain (§8)
  4. Solves a throwaway Scope2GoalModel(minimize_risk_only=True) → target_risk = R* (§6.4)
  5. Builds the real Scope2Parameters with targets (T*, P*, R*) and solves the full
     weighted goal-programming model → the balanced strategy
```

So every run of Model 2 **always re-solves Model 1 first** for that exact race/driver/constraint combination — $T^*$ is never a cached or historical number, it's the true current optimum under the current inputs. Likewise $R^*$ is freshly solved for, not assumed. Only $P^*$ (via `max_pit_stops`) is a direct user input rather than something solved for.

The formal `src/f1_optimizer/integration/` package (`pipeline.py`, `comparator.py`) sketches the same orchestration and a `StrategyComparator` for natural-language trade-off summaries, but those two files are intentionally left as stubs (`raise NotImplementedError`) — the live application performs this orchestration directly inside `BackendOptimizationRunner`, which is the implementation this document describes.

---

## 10. Validation Against Real Race Results

### 10.1 Bulk sanity validation — `scripts/validate_models.py`

Runs both Model 1 and Model 2 across every available (year, race) combination (or a `--quick` sample), and for each checks:
- solver status is `Optimal`,
- the stint lengths sum exactly to the race's total lap count,
- every stint has at least 1 lap,
- Model 1 and Model 2 agree on total race distance.

Results are streamed to `scripts/validation_report.csv` (one row per model per race) so a long run can be safely interrupted and resumed (`--resume`).

### 10.2 Real-world comparison — `scripts/compare_to_real.py`

For every race that passed validation, this script:
1. Finds the **fastest real finisher** (excluding anyone who didn't complete the race distance, within 1 lap), after filtering out laps inflated by red flags/Safety Cars (any lap $>3\times$ that race's median lap time is dropped — a true stoppage, not normal variance).
2. Re-solves both models for that race.
3. Computes
$$
\Delta_{\text{real}} = T_{\text{predicted}} - T_{\text{real, fastest finisher}}
$$
and records whether the predicted strategy's pit-stop count and compound sequence resemble the real one.

This produces `scripts/real_vs_predicted.csv`, from which average deltas and "beat the real fastest finisher" rates are printed per model — the practical check of whether the fitted degradation curves and pit-loss estimates produce *plausible* (not wildly optimistic or pessimistic) race times compared to what actually happened on track.

### 10.3 Formal validation module (design-level)

`src/f1_optimizer/common/validation/result_validator.py` defines the intended formal metric set for comparing a single predicted strategy against Kaggle ground truth:
$$
\text{Error}_{\text{time}} = \frac{|T_{\text{predicted}} - T_{\text{actual}}|}{T_{\text{actual}}} \times 100\%
$$
plus pit-stop count concordance and stint-transition-lap accuracy. This module is currently a stub (`NotImplementedError`) — the two scripts above are the methodology's actual, working validation layer.

---

## 11. Worked Numerical Example

Using a real row pair from `scripts/validation_report.csv` — **2018 Abu Dhabi Grand Prix**, $N=55$ laps:

| | Model 1 (MILP) | Model 2 (Goal Programming) |
|---|---|---|
| Pit-stop ceiling given | — | `max_pit_stops = 1` |
| Stints found | 2 | 2 |
| Pit stops | 1 | 1 |
| $P$ (pit loss, this circuit) | 22.96 s | 22.96 s |
| Total predicted race time | 5923.39 s | 5906.60 s |

Here Model 2 actually finds a slightly **faster** total than Model 1 for the same pit-stop count — this is possible because Model 1's objective purely minimizes time with only a *floor* on pit stops (so it may use more stops than strictly needed if that's faster), while Model 2 is given a tighter pit-stop ceiling as a hard input; the two models are answering related but not identical questions for this particular parameter set. The general expectation $T_{\text{balanced}} \ge T^*$ (§5.3) holds when both models are run with the **same** `min_pit_stops`/`max_pit_stops` window — see `tests/scope2/test_scope2.py` for the boundedness test that enforces this under matched constraints.

For a race requiring a genuine trade (e.g. forcing fewer stops than Model 1's free optimum would choose), the typical pattern is a small positive time delta, e.g. $\Delta T \approx +1.9\text{s}$ to save one stop — the headline trade-off number surfaced on the comparison screen (§5.6, point 3).

---

## 12. Glossary of Symbols

| Symbol | Meaning |
|---|---|
| $N$ | Total race laps |
| $C$ | Set of tyre compounds present in this race's data |
| $l$ | Lap index, $1,\dots,N$ |
| $c$ | Compound index |
| $x_{l,c}$ | 1 if compound $c$ active on lap $l$ |
| $p_l$ | 1 if a pit stop occurs after lap $l$ |
| $s_{l,c}$ | 1 if a new stint on $c$ starts at lap $l$ |
| $\text{age}_{l,c}$ | Consecutive laps $c$ has run, counting lap $l$ |
| $\ell_{l,c,k}$ | 1 if $\text{age}_{l,c} \le$ tier-$k$ threshold |
| $T_{l,c}$ | Predicted lap time for compound $c$ on lap $l$ |
| $\text{Base}_c$ | Fitted baseline pace (intercept) for compound $c$ |
| $\alpha_c$ | Fitted degradation rate (slope, s/lap) for compound $c$, floored at 0 |
| $P$ | Pit-stop time loss (seconds), race/circuit-specific |
| $L_c^{\max}$ | Max durable stint length for compound $c$ |
| $T^{*}$ | Model 1's solved fastest race time (Goal 1's target) |
| $P^{*}$ | User's `max_pit_stops` (Goal 2's target) |
| $R$ | Strategy's total degradation-risk score |
| $R^{*}$ | True minimum achievable risk score (Goal 3's target, solved for) |
| $d_k^+, d_k^-$ | Over-/under-achievement deviation for goal $k \in \{1,2,3\}$ |
| $w_1, w_2, w_3$ | Priority weights, $\sum w_k = 1$ |
| $Z$ | Model 2's weighted-deviation objective value |

---

### Where each piece lives in the code

| Concept | File |
|---|---|
| Dataset access | `src/f1_optimizer/common/data/dataset_loader.py` |
| Lap-time parsing | `src/f1_optimizer/common/utils/time_utils.py` |
| Degradation curve fitting (general) | `src/f1_optimizer/common/tyre/degradation_model.py` |
| Stint-life statistics | `src/f1_optimizer/common/statistics/tyre_statistics.py` |
| **All real parameter derivation, feasibility checks, T\*/R\* discovery** | `backend/app/services/runner.py` (`BackendOptimizationRunner`) |
| Model 1 formulation | `src/f1_optimizer/scope1/model/milp_model.py` |
| Model 1 parameters schema | `src/f1_optimizer/scope1/parameters/scope1_parameters.py` |
| Model 1 solving & extraction | `src/f1_optimizer/scope1/solver/milp_solver.py` |
| Model 2 formulation | `src/f1_optimizer/scope2/model/goal_model.py` |
| Model 2 parameters schema | `src/f1_optimizer/scope2/parameters/scope2_parameters.py` |
| Model 2 goals/weights | `src/f1_optimizer/scope2/goals/goal_definitions.py`, `weights.py` |
| Model 2 solving & extraction | `src/f1_optimizer/scope2/solver/goal_solver.py` |
| Bulk sanity validation | `scripts/validate_models.py` |
| Real-world comparison | `scripts/compare_to_real.py` |
| FastAPI endpoints | `backend/app/api/routes.py` |
