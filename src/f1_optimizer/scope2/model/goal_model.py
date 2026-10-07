"""Mathematical formulation for Scope 2 Goal Programming Model.

Decision Variables:
    x_{l,c} in {0,1}   - tyre compound c active on lap l
    p_l in {0,1}       - pit stop occurs after lap l
    d1+, d1-           - time goal deviation variables
    d2+, d2-           - pit-stop goal deviation variables
    d3+, d3-           - degradation goal deviation variables

Goals (Slide 14):
    Goal 1 (Time):        T + d1- - d1+ = T*
    Goal 2 (Pit stops):   P + d2- - d2+ = P*
    Goal 3 (Degradation): D + d3- - d3+ = D*

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

        d1_plus = pulp.LpVariable("d1_plus", lowBound=0)
        d1_minus = pulp.LpVariable("d1_minus", lowBound=0)
        d2_plus = pulp.LpVariable("d2_plus", lowBound=0)
        d2_minus = pulp.LpVariable("d2_minus", lowBound=0)
        d3_plus = pulp.LpVariable("d3_plus", lowBound=0)
        d3_minus = pulp.LpVariable("d3_minus", lowBound=0)

        total_time = pulp.lpSum(
            self.params.predicted_lap_times.get(lap, {}).get(compound, 0.0) * x[(lap, compound)]
            for lap in laps
            for compound in compounds
        )
        total_pit_stops = pulp.lpSum(p.values())
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

        model += total_time + d1_minus - d1_plus == self.params.targets.target_race_time_t_star
        model += total_pit_stops + d2_minus - d2_plus == self.params.targets.target_pit_stops_p_star
        model += degradation_index + d3_minus - d3_plus == self.params.targets.target_degradation_d_star

        model += (
            self.params.weights.weight_time_w1 * d1_plus
            + self.params.weights.weight_pit_stops_w2 * d2_plus
            + self.params.weights.weight_degradation_w3 * d3_plus
        )

        self._model = model
        return model
