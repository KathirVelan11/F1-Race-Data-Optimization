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

### Goal 1 — Race Time
Target $T^*$ is the fastest achievable race time obtained from Scope 1 (MILP):
$$T + d_1^- - d_1^+ = T^*$$
*Since $T^*$ is the absolute unconstrained minimum, $T \ge T^*$, meaning $d_1^- = 0$ and $d_1^+$ represents the time penalty accepted.*

### Goal 2 — Pit Stops
Target $P^*$ is the preferred pit-stop count (e.g., $P^* = 1$ stop):
$$P_{\text{stops}} + d_2^- - d_2^+ = P^*$$
*Here, $d_2^+$ represents additional pit stops beyond the preferred target.*

### Goal 3 — Tyre Degradation
Target $D^*$ is the target degradation threshold (rate of wear per lap):
$$D_{\text{deg}} + d_3^- - d_3^+ = D^*$$
*Here, $d_3^+$ represents degradation in excess of the desired threshold.*

---

## 4. Objective Function

Minimize the weighted sum of unfavorable deviations:
$$\min Z = w_1 d_1^+ + w_2 d_2^+ + w_3 d_3^+$$

Subject to:
$$w_1 + w_2 + w_3 = 1, \quad w_k \ge 0$$

### Example Weight Configuration (PPT Slide 14)
- $w_1 = 0.50$ (Time penalty priority)
- $w_2 = 0.25$ (Pit-stop avoidance priority)
- $w_3 = 0.25$ (Tyre preservation priority)

---

## 5. Model Output

1. Balanced stint structure and pit stop laps.
2. Achieved race time $T_{\text{balanced}}$.
3. Trade-off delta: $\Delta T = T_{\text{balanced}} - T^*$ (e.g. $+1.9$ seconds for saving 1 pit stop).
4. Direct comparison table versus Scope 1.
