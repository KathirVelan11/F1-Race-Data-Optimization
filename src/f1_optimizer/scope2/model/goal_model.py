"""Mathematical formulation for Scope 2 Goal Programming Model.

Decision Variables:
    x_{l,c} in {0,1}   - tyre compound c active on lap l
    p_l in {0,1}       - pit stop occurs after lap l
    d1+, d1-           - time goal deviation variables
    d2+, d2-           - pit-stop goal deviation variables
    d3+, d3-           - degradation goal deviation variables

Goals, normalized by their own target so d1+/d2+/d3+ are comparable fractional
deviations (0 = exactly on target) rather than raw units of wildly different scale
(seconds in the thousands vs a stop count of ~1-3 vs a 0-1 index) -- without this,
w1/w2/w3 cannot meaningfully trade off against each other, since even a tiny absolute
time deviation (tens of seconds) numerically dwarfs the entire possible range of the
pit-stop or degradation penalty:
    Goal 1 (Time):        T/T* + d1- - d1+ = 1
    Goal 2 (Pit stops):   P/P* + d2- - d2+ = 1
    Goal 3 (Degradation): D/D* + d3- - d3+ = 1

Objective:
    min Z = w1 * d1+ + w2 * d2+ + w3 * d3+

Subject to:
    Standard race assignment constraints (a)-(f)
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
        degradation_index = pulp.lpSum(
            self.params.compound_degradations.get(compound, 0.0) * x[(lap, compound)]
            for lap in laps
            for compound in compounds
        ) / self.params.total_laps

        for lap in laps:
            model += pulp.lpSum(x[(lap, compound)] for compound in compounds) == 1

        for lap in range(1, self.params.total_laps):
            for compound in compounds:
                model += p[lap] >= x[(lap, compound)] - x[(lap + 1, compound)]
                model += p[lap] >= x[(lap + 1, compound)] - x[(lap, compound)]

        model += total_pit_stops <= self.params.max_pit_stops

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

        # Normalize each goal by its own target so d1+/d2+/d3+ are comparable fractional
        # deviations (see module docstring) -- a target of 0 would make division
        # meaningless, so such a goal falls back to an un-normalized (raw-unit) constraint,
        # which only happens for a goal that's already trivially at/near zero anyway.
        time_target = self.params.targets.target_race_time_t_star
        pit_stops_target = self.params.targets.target_pit_stops_p_star
        degradation_target = self.params.targets.target_degradation_d_star

        time_scale = time_target if time_target > 0 else 1.0
        pit_stops_scale = pit_stops_target if pit_stops_target > 0 else 1.0
        degradation_scale = degradation_target if degradation_target > 0 else 1.0

        model += (total_time / time_scale) + d1_minus - d1_plus == (time_target / time_scale)
        model += (total_pit_stops / pit_stops_scale) + d2_minus - d2_plus == (pit_stops_target / pit_stops_scale)
        model += (degradation_index / degradation_scale) + d3_minus - d3_plus == (degradation_target / degradation_scale)

        model += (
            self.params.weights.weight_time_w1 * d1_plus
            + self.params.weights.weight_pit_stops_w2 * d2_plus
            + self.params.weights.weight_degradation_w3 * d3_plus
        )

        self._model = model
        return model
