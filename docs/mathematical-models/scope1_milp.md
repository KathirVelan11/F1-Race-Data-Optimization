# Scope 1: Integrated Tyre & Pit-Stop Strategy (MILP)

**Course:** Operations Research (Course Project - Team B13)  
**Model Type:** Mixed-Integer Linear Programming (MILP)  
**Primary Reference:** Presentation Slides 9–11  

---

## 1. Problem Formulation

Find the single fastest possible race strategy by deciding:
- How many pit stops to make ($\le 2$)
- On which exact laps to make the pit stops
- Which tyre compound to use in each stint

The objective is to minimize total predicted race time while satisfying tyre durability, stint length, and regulatory constraints.

---

## 2. Sets and Indices

- $l \in \{1, 2, \dots, N\}$: Set of race laps, where $N$ is the total race distance.
- $c \in \{S, M, H\}$: Set of dry tyre compounds:
  - $S$: Soft compound (fastest pace, highest degradation)
  - $M$: Medium compound (balanced pace and durability)
  - $H$: Hard compound (slower pace, lowest degradation)

---

## 3. Decision Variables

- $x_{l,c} \in \{0, 1\}$: Binary variable; equals $1$ if compound $c$ is active on lap $l$, $0$ otherwise.
- $p_l \in \{0, 1\}$: Binary variable; equals $1$ if a pit stop occurs after lap $l$, $0$ otherwise.

---

## 4. Parameters

- $T_{l,c}$: Predicted lap time on compound $c$ on lap $l$ at current tyre age.
- $P$: Fixed pit-stop time loss ($P \approx 13$ seconds in MILP formulation slide; sensitivity tested up to $\approx 20$ seconds).
- $L_c^{\max}$: Maximum durable stint length for compound $c$ (e.g., $L_S^{\max} = 25$, $L_M^{\max} = 40$, $L_H^{\max} = 55$).
- $N$: Total race laps.

---

## 5. Objective Function

$$\min T_{\text{race}} = \sum_{l=1}^N \sum_{c \in \{S,M,H\}} T_{l,c} \cdot x_{l,c} + P \sum_{l=1}^N p_l$$

---

## 6. Constraints

### (a) Compound Exclusivity
Exactly one tyre compound must be active on each lap:
$$\sum_{c \in \{S,M,H\}} x_{l,c} = 1 \quad \forall l \in \{1, \dots, N\}$$

### (b) Pit Stop Limit
A driver may make at most 2 pit stops during the race:
$$\sum_{l=1}^N p_l \le 2$$

### (c) Tyre Durability
Tyre age cannot exceed the compound's maximum durable stint length:
$$\text{TyreAge}_{l,c} \le L_c^{\max} \quad \forall l, c$$

### (d) Minimum Stint Length
To prevent frivolous pit stops and ensure strategic realism:
$$\text{stint length} \ge 5 \text{ laps}$$

### (e) Full Race Distance Coverage
The sum of all stint lengths must exactly equal the scheduled race distance:
$$\sum_{i} \text{stint}_i = N$$

### (f) Binary Integrality
$$x_{l,c} \in \{0, 1\} \quad \forall l, c$$
$$p_l \in \{0, 1\} \quad \forall l$$

---

## 7. Model Output

The optimal values of $x_{l,c}^*$ and $p_l^*$ yield:
1. Optimal pit-stop laps: $\{l \mid p_l^* = 1\}$.
2. Tyre compound fitted for each stint.
3. Minimum predicted total race time: $T^* = T_{\text{race}}^*$.
