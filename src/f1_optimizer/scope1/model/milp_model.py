"""Mathematical formulation for Scope 1 MILP Tyre & Pit-Stop Strategy.

Objective:
    min T_race = sum_{l=1}^N sum_c (alpha_c * x_{l,c} + beta_c * age_{l,c}) + P * sum_{l=1}^N p_l

    alpha_c / beta_c are the fitted base pace / degradation rate per compound.
    age_{l,c} is TRUE tyre age (laps since that compound was last fitted), not the
    race-lap number -- using race-lap number instead would treat a tyre fitted mid-race
    as already worn, which biases the solver against later pit stops. See age_{l,c}
    below and Scope2GoalModel, which uses the identical construction.

Constraints:
    (a) sum_c x_{l,c} = 1                    forall l in {1, ..., N}
    (b) sum_{l=1}^N p_l >= min_pit_stops     (user must pit at least this many times)
    (c) TyreAge_{l,c} <= L_c^max            forall l, c
    (d) stint length >= min_stint_length
    (e) sum_i stint_i = N
    (f) x_{l,c} in {0,1}, p_l in {0,1}
    (g) sum_l start_{l,c} <= max_sets_c      forall c (tyre-set allocation limit --
                                               this is the real-world ceiling on pit
                                               stops, since each stint consumes one set)

Decision Variables:
    x_{l,c} = 1 if compound c is used on lap l, 0 otherwise
    p_l = 1 if a pit stop occurs after lap l, 0 otherwise
    start_{l,c} = 1 if a new stint on compound c begins on lap l, 0 otherwise
    age_{l,c} = consecutive laps compound c has run, counting lap l itself (0 if c is
                not active on lap l; 1 on the first lap of a new stint)
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

        for lap in laps:
            model += pulp.lpSum(x[(lap, compound)] for compound in compounds) == 1

        for lap in range(1, self.params.total_laps):
            for compound in compounds:
                model += p[lap] >= x[(lap, compound)] - x[(lap + 1, compound)]
                model += p[lap] >= x[(lap + 1, compound)] - x[(lap, compound)]

        model += pulp.lpSum(p.values()) >= self.params.min_pit_stops

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

        for compound in compounds:
            model += (
                pulp.lpSum(start[(lap, compound)] for lap in laps)
                <= self.params.max_sets_per_compound.get(compound, self.params.total_laps)
            )

        # --- Tyre-age tracking (mirrors Scope2GoalModel) ------------------------------
        # age[l,c] = consecutive laps compound c has been running, counting lap l itself
        # (0 if c isn't active on lap l; 1 on the first lap of a stint, matching how
        # TyreDegradationModel fits degradation against tyre age starting at 1). Built
        # from `start` with standard big-M chaining: age resets to 1 when a new stint
        # starts, otherwise increments from the prior lap.
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

        # Race time, using TRUE tyre age (not race lap number): base_pace[c] * x[l,c] +
        # degradation_rate[c] * age[l,c]. age[l,c] is already forced to 0 whenever
        # x[l,c]=0, so this is a correct linear cost with no bilinear (age * x) term
        # needed -- a fresh tyre fitted mid-race costs base_pace + degradation_rate*1
        # regardless of what race lap it started on, instead of being penalized as if it
        # already had that many laps of wear.
        model += (
            pulp.lpSum(
                self.params.compound_base_pace.get(compound, 0.0) * x[(lap, compound)]
                + self.params.compound_degradation_rate.get(compound, 0.0) * age[(lap, compound)]
                for lap in laps
                for compound in compounds
            )
            + self.params.pit_loss_p * pulp.lpSum(p.values())
        )

        self.age = age
        self._model = model
        return model
