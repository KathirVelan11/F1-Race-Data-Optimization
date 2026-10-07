"""Mathematical formulation for Scope 1 MILP Tyre & Pit-Stop Strategy.

Objective:
    min T_race = sum_{l=1}^N T_{l,c} + P * sum_{l=1}^N p_l

Constraints:
    (a) sum_c x_{l,c} = 1                    forall l in {1, ..., N}
    (b) sum_{l=1}^N p_l <= 2
    (c) TyreAge_{l,c} <= L_c^max            forall l, c
    (d) stint length >= 5
    (e) sum_i stint_i = N
    (f) x_{l,c} in {0,1}, p_l in {0,1}

Decision Variables:
    x_{l,c} = 1 if compound c is used on lap l, 0 otherwise
    p_l = 1 if a pit stop occurs after lap l, 0 otherwise
"""
from typing import Any

import pulp

from src.f1_optimizer.scope1.parameters.scope1_parameters import Scope1Parameters


class Scope1MilpModel:
    """Builder for the Scope 1 Mixed-Integer Linear Programming Model."""

    def __init__(self, parameters: Scope1Parameters):
        self.params = parameters
        self._model: Any = None

    def build(self) -> Any:
        """Construct the MILP decision variables, objective function, and constraints."""
        if self._model is not None:
            return self._model

        laps = range(1, self.params.total_laps + 1)
        compounds = self.params.compounds

        model = pulp.LpProblem("Scope1_Fastest_Strategy", pulp.LpMinimize)

        x = {
            (lap, compound): pulp.LpVariable(
                f"x_{lap}_{compound}",
                lowBound=0,
                upBound=1,
                cat="Binary",
            )
            for lap in laps
            for compound in compounds
        }

        p = {
            lap: pulp.LpVariable(f"p_{lap}", lowBound=0, upBound=1, cat="Binary")
            for lap in range(1, self.params.total_laps)
        }

        start = {
            (lap, compound): pulp.LpVariable(
                f"s_{lap}_{compound}",
                lowBound=0,
                upBound=1,
                cat="Binary",
            )
            for lap in laps
            for compound in compounds
        }

        model += (
            pulp.lpSum(
                self.params.predicted_lap_times.get(lap, {}).get(compound, 0.0) * x[(lap, compound)]
                for lap in laps
                for compound in compounds
            )
            + self.params.pit_loss_p * pulp.lpSum(p.values())
        )

        for lap in laps:
            model += pulp.lpSum(x[(lap, compound)] for compound in compounds) == 1

        for lap in range(1, self.params.total_laps):
            for compound in compounds:
                model += p[lap] >= x[(lap, compound)] - x[(lap + 1, compound)]
                model += p[lap] >= x[(lap + 1, compound)] - x[(lap, compound)]

        model += pulp.lpSum(p.values()) <= self.params.max_pit_stops

        for lap in laps:
            for compound in compounds:
                model += start[(lap, compound)] <= x[(lap, compound)]

                if lap == 1:
                    model += start[(lap, compound)] == x[(lap, compound)]
                else:
                    model += start[(lap, compound)] <= 1 - x[(lap - 1, compound)]
                    model += start[(lap, compound)] >= x[(lap, compound)] - x[(lap - 1, compound)]

                # Any stint that starts on this lap must contain at least the minimum runnable length.
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

        self._model = model
        return model
