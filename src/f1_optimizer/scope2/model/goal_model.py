"""Mathematical formulation for Scope 2 Goal Programming Model.

Decision Variables:
    x_{l,c} in {0,1}     - tyre compound c active on lap l
    p_l in {0,1}         - pit stop occurs after lap l
    age_{l,c} >= 0       - consecutive laps compound c has run, counting lap l (0 if
                           c isn't active on lap l)
    le_k{l,c} in {0,1}   - 1 iff age_{l,c} <= tier k's threshold (k=1,2,3; see risk below)
    d1+, d1-             - time goal deviation variables
    d2+, d2-             - pit-stop goal deviation variables
    d3+, d3-             - degradation-risk goal deviation variables

Goal 3 (degradation risk) replaces a flat per-compound index with a genuine per-lap,
age-aware risk score: each lap's tyre age is bucketed into 4 tiers (0=low to 3=very
high) scaled to that compound's own real durability, and the strategy's total risk is
the sum of every lap's tier weight. This makes risk a real trade-off the optimizer
weighs against time/pit-stops (a strategy that runs a compound deep into its high-risk
zone costs more here, even if it's marginally faster), rather than a static label.

Goals, normalized by their own target so d1+/d2+/d3+ are comparable fractional
deviations (0 = exactly on target) rather than raw units of wildly different scale --
without this, w1/w2/w3 cannot meaningfully trade off against each other:
    Goal 1 (Time):   T/T* + d1- - d1+ = 1
    Goal 2 (Stops):  P/P* + d2- - d2+ = 1
    Goal 3 (Risk):   R/R* + d3- - d3+ = 1   (R = sum of per-lap risk-tier weights)

Objective:
    min Z = w1 * d1+ + w2 * d2+ + w3 * d3+

Subject to:
    Standard race assignment constraints (a)-(f), plus age-tracking and risk-tier
    derivation constraints (see build() for the full big-M encoding).
"""
from typing import Any

import pulp

from src.f1_optimizer.scope2.parameters.scope2_parameters import Scope2Parameters


class Scope2GoalModel:
    """Builder for Scope 2 Goal Programming Model."""

    def __init__(self, parameters: Scope2Parameters):
        self.params = parameters
        self._model: Any = None

    def build(self) -> Any:
        """Construct the Goal Programming decision variables, goals, and penalty objective."""
        if self._model is not None:
            return self._model

        laps = range(1, self.params.total_laps + 1)
        compounds = self.params.compounds

        model = pulp.LpProblem("Scope2_Balanced_Strategy", pulp.LpMinimize)

        x = {
            (lap, compound): pulp.LpVariable(f"x_{lap}_{compound}", lowBound=0, upBound=1, cat="Binary")
            for lap in laps
            for compound in compounds
        }

        p = {
            lap: pulp.LpVariable(f"p_{lap}", lowBound=0, upBound=1, cat="Binary")
            for lap in range(1, self.params.total_laps)
        }

        start = {
            (lap, compound): pulp.LpVariable(f"s_{lap}_{compound}", lowBound=0, upBound=1, cat="Binary")
            for lap in laps
            for compound in compounds
        }

        d1_plus = pulp.LpVariable("d1_plus", lowBound=0)
        d1_minus = pulp.LpVariable("d1_minus", lowBound=0)
        d2_plus = pulp.LpVariable("d2_plus", lowBound=0)
        d2_minus = pulp.LpVariable("d2_minus", lowBound=0)
        d3_plus = pulp.LpVariable("d3_plus", lowBound=0)
        d3_minus = pulp.LpVariable("d3_minus", lowBound=0)

        total_pit_stops = pulp.lpSum(p.values())
        total_time = (
            pulp.lpSum(
                self.params.predicted_lap_times.get(lap, {}).get(compound, 0.0) * x[(lap, compound)]
                for lap in laps
                for compound in compounds
            )
            + self.params.pit_loss_p * total_pit_stops
        )
        for lap in laps:
            model += pulp.lpSum(x[(lap, compound)] for compound in compounds) == 1

        for lap in range(1, self.params.total_laps):
            for compound in compounds:
                model += p[lap] >= x[(lap, compound)] - x[(lap + 1, compound)]
                model += p[lap] >= x[(lap + 1, compound)] - x[(lap, compound)]

        model += total_pit_stops >= self.params.min_pit_stops

        for lap in laps:
            for compound in compounds:
                model += start[(lap, compound)] <= x[(lap, compound)]

                if lap == 1:
                    model += start[(lap, compound)] == x[(lap, compound)]
                else:
                    model += start[(lap, compound)] <= 1 - x[(lap - 1, compound)]
                    model += start[(lap, compound)] >= x[(lap, compound)] - x[(lap - 1, compound)]

                min_end = min(self.params.total_laps, lap + self.params.min_stint_length - 1)
                model += (
                    pulp.lpSum(x[(future_lap, compound)] for future_lap in range(lap, min_end + 1))
                    >= self.params.min_stint_length * start[(lap, compound)]
                )

                max_end = min(self.params.total_laps, lap + self.params.max_stint_durability.get(compound, self.params.total_laps))
                model += (
                    pulp.lpSum(x[(future_lap, compound)] for future_lap in range(lap, max_end + 1))
                    <= self.params.max_stint_durability.get(compound, self.params.total_laps)
                    + (self.params.total_laps + 1) * (1 - start[(lap, compound)])
                )

        for lap in laps:
            model += pulp.lpSum(start[(lap, compound)] for compound in compounds) <= 1

        for compound in compounds:
            model += (
                pulp.lpSum(start[(lap, compound)] for lap in laps)
                <= self.params.max_sets_per_compound.get(compound, self.params.total_laps)
            )

        # --- Tyre-age tracking and degradation-risk tiers -----------------------------
        # age[l,c] = consecutive laps compound c has been running, counting lap l itself
        # (0 if c isn't active on lap l). Built from `start` with standard big-M chaining:
        # age resets to 1 when a new stint starts, otherwise increments from the prior lap.
        #
        # big_m is scoped PER COMPOUND to that compound's own max_stint_durability (not
        # the full race distance) -- age can never legitimately exceed durability given
        # the existing stint-length constraints, and a much smaller, per-compound big-M
        # keeps the LP relaxation tight, which matters a lot for CBC's solve time once
        # this many binary variables are in play. age is also declared Integer (tyre age
        # is inherently a whole number of laps), which further tightens the branch space
        # versus a continuous relaxation.
        age = {
            (lap, compound): pulp.LpVariable(
                f"age_{lap}_{compound}", lowBound=0,
                upBound=self.params.max_stint_durability.get(compound, self.params.total_laps),
                cat="Integer",
            )
            for lap in laps
            for compound in compounds
        }
        for compound in compounds:
            big_m_c = self.params.max_stint_durability.get(compound, self.params.total_laps) + 1
            for lap in laps:
                model += age[(lap, compound)] <= big_m_c * x[(lap, compound)]
                if lap == 1:
                    model += age[(lap, compound)] >= x[(lap, compound)]
                    model += age[(lap, compound)] <= x[(lap, compound)]
                else:
                    prev_age = age[(lap - 1, compound)]
                    model += age[(lap, compound)] <= prev_age + 1 + big_m_c * (1 - x[(lap, compound)])
                    model += age[(lap, compound)] >= prev_age + 1 - big_m_c * (1 - x[(lap, compound)]) - big_m_c * start[(lap, compound)]
                    model += age[(lap, compound)] <= 1 + big_m_c * (1 - start[(lap, compound)])
                    model += age[(lap, compound)] >= 1 - big_m_c * (1 - start[(lap, compound)])

        # Risk tiers: for each (lap, compound), derive a cumulative risk-tier score from
        # tyre age, scaled to that compound's own durability (Scope2Parameters.risk_tiers).
        # le_k[l,c] = 1 iff age[l,c] <= t_k (the compound's k-th tier threshold). These are
        # naturally nested (age <= t1 implies age <= t2 implies age <= t3, since
        # t1 < t2 < t3), so le1 <= le2 <= le3 always holds once the big-M upper bound
        # below is enforced; no separate ordering constraint is needed.
        #
        # The risk penalty for a lap is (3 - le1 - le2 - le3): all three satisfied (age in
        # the lowest tier) scores 0, none satisfied (age beyond t3, i.e. very high risk)
        # scores 3. Because this is being minimized in the objective (Goal 3 wants LOW
        # risk), the solver is naturally driven to push age down / le_k up wherever
        # possible -- there is no incentive to under-claim le_k=0 when age truly
        # qualifies, since that would only inflate its own risk score. A lap where the
        # compound isn't active (x=0, age=0) always trivially satisfies age<=t_k, so its
        # risk penalty is correctly 0 and doesn't need separate handling.
        tier_bounds = {
            compound: self.params.risk_tiers.get(compound, [
                max(1, self.params.total_laps // 3),
                max(2, self.params.total_laps * 2 // 3),
                max(3, self.params.total_laps * 9 // 10),
            ])
            for compound in compounds
        }
        le = {
            (lap, compound, k): pulp.LpVariable(f"le{k}_{lap}_{compound}", lowBound=0, upBound=1, cat="Binary")
            for lap in laps
            for compound in compounds
            for k in (1, 2, 3)
        }
        for compound in compounds:
            t1, t2, t3 = tier_bounds[compound]
            tier_big_m = self.params.max_stint_durability.get(compound, self.params.total_laps)
            for lap in laps:
                a = age[(lap, compound)]
                le1, le2, le3 = le[(lap, compound, 1)], le[(lap, compound, 2)], le[(lap, compound, 3)]
                model += a <= t1 + tier_big_m * (1 - le1)
                model += a <= t2 + tier_big_m * (1 - le2)
                model += a <= t3 + tier_big_m * (1 - le3)

        risk_score = pulp.lpSum(
            (3 - le[(lap, compound, 1)] - le[(lap, compound, 2)] - le[(lap, compound, 3)])
            for lap in laps
            for compound in compounds
        )

        # Normalize each goal by its own target so d1+/d2+/d3+ are comparable fractional
        # deviations (see module docstring) -- a target of 0 would make division

        # Normalize each goal by its own target so d1+/d2+/d3+ are comparable fractional
        # deviations (see module docstring) -- a target of 0 would make division
        # meaningless, so such a goal falls back to an un-normalized (raw-unit) constraint,
        # which only happens for a goal that's already trivially at/near zero anyway.
        time_target = self.params.targets.target_race_time_t_star
        pit_stops_target = self.params.targets.target_pit_stops_p_star
        risk_target = self.params.targets.target_degradation_d_star

        time_scale = time_target if time_target > 0 else 1.0
        pit_stops_scale = pit_stops_target if pit_stops_target > 0 else 1.0
        risk_scale = risk_target if risk_target > 0 else 1.0

        model += (total_time / time_scale) + d1_minus - d1_plus == (time_target / time_scale)
        model += (total_pit_stops / pit_stops_scale) + d2_minus - d2_plus == (pit_stops_target / pit_stops_scale)
        model += (risk_score / risk_scale) + d3_minus - d3_plus == (risk_target / risk_scale)

        model += (
            self.params.weights.weight_time_w1 * d1_plus
            + self.params.weights.weight_pit_stops_w2 * d2_plus
            + self.params.weights.weight_degradation_w3 * d3_plus
        )

        self._model = model
        return model
