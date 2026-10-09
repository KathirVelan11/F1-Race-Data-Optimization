# Scope 2: Multi-Objective Strategy Selection (Goal Programming)

**Course:** Operations Research (Course Project - Team B13)  
**Model Type:** Goal Programming with Weighted Deviations  
**Primary Reference:** Presentation Slides 12–14  

---

## 1. Problem Formulation

Real Formula 1 race teams rarely optimize on total race time alone. Pit stops entail operational risks (stuck wheel guns, cross-threaded wheel nuts, unsafe pit lane releases), and excessive tyre degradation risks sudden grip loss and structural degradation.

The Goal Programming model finds a **balanced race strategy** by trading a small amount of race time to reduce pit-stop count and tyre degradation, guided by team-assigned priority weights.

---

## 2. Decision Variables

- $x_{l,c} \in \{0, 1\}$: Compound $c$ active on lap $l$.
- $p_l \in \{0, 1\}$: Pit stop occurs after lap $l$.
- $d_1^+, d_1^- \ge 0$: Deviation variables for Goal 1 (Time).
- $d_2^+, d_2^- \ge 0$: Deviation variables for Goal 2 (Pit-Stop Count).
- $d_3^+, d_3^- \ge 0$: Deviation variables for Goal 3 (Tyre Degradation).

Where:
- $d_k^+$: Over-achievement of goal target $k$.
- $d_k^-$: Under-achievement of goal target $k$.

---

## 3. The Three Strategic Goals

Each goal is normalized by dividing through by its own target, so $d_1^+, d_2^+, d_3^+$
are comparable *fractional* deviations (0 = exactly on target) instead of raw units of
wildly different scale (seconds vs. a stop count vs. a risk score). Without this,
$w_1/w_2/w_3$ could not meaningfully trade off against each other — see
`src/f1_optimizer/scope2/model/goal_model.py`.

### Goal 1 — Race Time
Target $T^*$ is the fastest achievable race time, the real solved optimum of Scope 1 (MILP):
$$\frac{T}{T^*} + d_1^- - d_1^+ = 1$$
*$T^*$ is the unconstrained minimum, so in practice $T \ge T^*$: $d_1^-$ stays 0 and
$d_1^+$ is the fractional time penalty accepted for a better Goal 2/3 outcome.*

### Goal 2 — Pit Stops
Target $P^*$ is the **user's `max_pit_stops` input**, taken directly (not a historical
or data-derived estimate):
$$\frac{P_{\text{stops}}}{P^*} + d_2^- - d_2^+ = 1$$
*`max_pit_stops` is also enforced as a genuine hard ceiling on $P_{\text{stops}}$ in
Model 2 (on top of the existing `min_pit_stops` floor), so $d_2^+$ in practice measures
how far a strategy sits below that ceiling being used as a preferred, not just maximum,
value.*

### Goal 3 — Tyre Degradation Risk
$R$ is the strategy's total degradation-risk score: each lap's tyre age is bucketed into
4 tiers (0 = low .. 3 = very high), scaled to that compound's own real durability, and
summed across every lap of the race (see `BackendOptimizationRunner._get_degradation_risk_tiers`).
Target $R^*$ is the **true minimum risk score achievable** under this race's actual
constraints (min/max pit stops, min stint length, tyre-set and risk-ceiling limits) —
found by solving the same model with its objective swapped to `minimize R` alone, before
the real balanced solve (`BackendOptimizationRunner._get_min_achievable_risk_score`,
`Scope2GoalModel.__init__`'s `minimize_risk_only` flag). This mirrors how $T^*$ is
already Model 1's own solved optimum rather than an assumed value.

$$\frac{R}{R^*} + d_3^- - d_3^+ = 1$$

*$R^*$ is **not** fixed at 0: a tyre cannot physically stay in the lowest risk tier for
an entire stint once it must run at least `min_stint_length` laps, so an unreachable
$R^*=0$ would leave every strategy with the same unavoidable $d_3^+$ floor and no real
pressure to minimize risk further. Using the true achievable floor instead keeps
$d_3^+=0$ reachable by the best strategy, exactly like Goals 1 and 2, while still
pushing the optimizer toward fresher tyres above that floor.*

Per-compound hard risk ceilings (`max_risk_tier_per_compound`, optional, e.g. "never let
SOFT exceed Moderate") remain a separate, absolute safety bound enforced regardless of
weights — Goal 3 is the *preference* layered on top of that bound, not a replacement
for it.

---

## 4. Objective Function

Minimize the weighted sum of unfavorable (overshoot) deviations:
$$\min Z = w_1 d_1^+ + w_2 d_2^+ + w_3 d_3^+$$

Subject to:
$$w_1 + w_2 + w_3 = 1, \quad w_k \ge 0$$

Only the overshoot terms ($d_k^+$) are penalized — undershooting a target (faster than
$T^*$, fewer stops than $P^*$, lower risk than $R^*$) is always free, never discouraged.
$d_k^-$ exists purely so each goal equation stays solvable (balances to 1) in that case.

### Default Weight Configuration (PPT Slide 14)
- $w_1 = 0.50$ (Time penalty priority)
- $w_2 = 0.25$ (Pit-stop avoidance priority)
- $w_3 = 0.25$ (Tyre preservation priority)

User-adjustable in the UI; `GoalWeights` enforces the sum-to-1 rule.

---

## 5. Model Output

1. Balanced stint structure and pit stop laps.
2. Achieved race time $T_{\text{balanced}}$.
3. Trade-off delta: $\Delta T = T_{\text{balanced}} - T^*$ (e.g. $+1.9$ seconds for saving 1 pit stop).
4. Achieved deviations $d_1^+, d_2^+, d_3^+$ and risk score $R$.
5. Direct comparison table versus Scope 1.

---

## 6. User Inputs (Model 2)

| Input | Scope | Effect |
|---|---|---|
| `min_pit_stops` | Model 1 & 2 | Hard floor on pit-stop count. |
| `max_pit_stops` | Model 2 only | Hard ceiling on pit-stop count, **and** sets Goal 2's target $P^*$ directly. Must be $\ge$ `min_pit_stops`; a request with `max_pit_stops < min_pit_stops` is rejected with a clear message rather than silently clamped. Blank defaults to `min_pit_stops` itself. |
| `min_stint_length` | Model 1 & 2 | Minimum laps any stint must run once started. |
| `max_sets_per_compound` | Model 1 & 2 | Tyre-set allocation ceiling per compound. |
| `max_risk_tier_per_compound` | Model 2 only | Optional absolute hard ceiling per compound, independent of $R^*$/weights. |
| `weights` ($w_1, w_2, w_3$) | Model 2 only | Relative priority across the three goals; must sum to 1. |

$T^*$ and $R^*$ are always computed server-side (solved optima), never user-supplied —
only $P^*$ (via `max_pit_stops`) is a direct user input.
