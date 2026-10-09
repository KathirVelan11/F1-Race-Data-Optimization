"""Solver interface and execution for Scope 2 Goal Programming model."""
import time
from typing import Any, Dict, List

import pulp

from src.f1_optimizer.common.schemas.race import TyreCompound
from src.f1_optimizer.common.schemas.strategy import StintPlan
from src.f1_optimizer.scope2.goals.goal_definitions import GoalDeviations
from src.f1_optimizer.scope2.model.goal_model import Scope2GoalModel
from src.f1_optimizer.scope2.output.scope2_result import Scope2OptimizationResult
from src.f1_optimizer.scope2.parameters.scope2_parameters import Scope2Parameters


class Scope2GoalSolver:
    """Invokes solver for the Goal Programming model."""

    def __init__(self, solver_name: str = "HiGHS", time_limit_seconds: int = 20):
        """`solver_name` selects the backend ("HiGHS" or "PULP_CBC_CMD"). HiGHS is the
        default: it's free (no license), and in practice noticeably faster than CBC on
        this project's MILP/Goal-Programming models, especially the larger risk-tier
        formulation (age-tracking adds a lot of binary variables).

        `time_limit_seconds` caps how long the solver searches: a strategy that's merely
        very good (but not provably optimal) returned in a bounded time is far more
        useful to a user than making them wait indefinitely for a proof of optimality.
        """
        self.solver_name = solver_name
        self.time_limit_seconds = time_limit_seconds

    def _build_solver(self) -> Any:
        if self.solver_name == "HiGHS":
            return pulp.HiGHS(msg=False, timeLimit=self.time_limit_seconds)
        return pulp.PULP_CBC_CMD(msg=False, timeLimit=self.time_limit_seconds)

    def _extract_lap_compounds(self, model: Any, parameters: Scope2Parameters) -> Dict[int, str]:
        """Extract the selected compound for each lap from the solved model."""
        lap_compounds: Dict[int, str] = {}
        for lap in range(1, parameters.total_laps + 1):
            best_compound = None
            best_value = -1.0
            for compound in parameters.compounds:
                value = pulp.value(model.variablesDict()[f"x_{lap}_{compound}"])
                if value is not None and value > best_value:
                    best_value = value
                    best_compound = compound
            if best_compound is None:
                # Fallback tie-break only (no solved x-values at all for this lap) --
                # a fresh-tyre (age=1) pace comparison, since there's no stint context
                # available here to know true age.
                best_compound = min(
                    parameters.compounds,
                    key=lambda item: (
                        parameters.compound_base_pace.get(item, float("inf"))
                        + parameters.compound_degradation_rate.get(item, 0.0)
                    ),
                )
            lap_compounds[lap] = best_compound
        return lap_compounds

    @staticmethod
    def _stint_time(parameters: Scope2Parameters, compound: str, stint_length: int) -> float:
        """True predicted time for a stint of this compound and length, using tyre age
        1..stint_length (NOT race-lap number) -- sum_{age=1}^{len} (base + rate*age)."""
        base = parameters.compound_base_pace.get(compound, 0.0)
        rate = parameters.compound_degradation_rate.get(compound, 0.0)
        return stint_length * base + rate * (stint_length * (stint_length + 1) / 2)

    def _normalize_to_valid_stints(
        self,
        lap_compounds: Dict[int, str],
        parameters: Scope2Parameters,
    ) -> Dict[int, str]:
        """Guardrail for realistic strategy generation: split any block that violates stint limits."""
        normalized: Dict[int, str] = {}
        current_compound = None
        stint_start = 1

        for lap in range(1, parameters.total_laps + 1):
            compound = lap_compounds.get(lap, current_compound)
            if current_compound is None:
                current_compound = compound
                stint_start = lap
                continue

            if compound != current_compound:
                block_start = stint_start
                block_end = lap - 1
                block_len = block_end - block_start + 1
                durability = parameters.max_stint_durability.get(current_compound, block_len)
                min_length = parameters.min_stint_length

                cursor = block_start
                while cursor <= block_end:
                    remaining = block_end - cursor + 1
                    if remaining <= durability:
                        chunk_end = block_end
                    elif remaining - durability < min_length:
                        chunk_end = block_end - min_length
                    else:
                        chunk_end = cursor + durability - 1

                    if chunk_end < cursor:
                        chunk_end = block_end

                    for lap_idx in range(cursor, chunk_end + 1):
                        normalized[lap_idx] = current_compound

                    cursor = chunk_end + 1

                current_compound = compound
                stint_start = lap

        if current_compound is not None:
            block_start = stint_start
            block_end = parameters.total_laps
            block_len = block_end - block_start + 1
            durability = parameters.max_stint_durability.get(current_compound, block_len)
            min_length = parameters.min_stint_length

            cursor = block_start
            while cursor <= block_end:
                remaining = block_end - cursor + 1
                if remaining <= durability:
                    chunk_end = block_end
                elif remaining - durability < min_length:
                    chunk_end = block_end - min_length
                else:
                    chunk_end = cursor + durability - 1

                if chunk_end < cursor:
                    chunk_end = block_end

                for lap_idx in range(cursor, chunk_end + 1):
                    normalized[lap_idx] = current_compound

                cursor = chunk_end + 1

        for lap in range(1, parameters.total_laps + 1):
            if lap not in normalized:
                normalized[lap] = lap_compounds.get(lap, parameters.compounds[0] if parameters.compounds else "SOFT")

        return normalized

    def solve(self, parameters: Scope2Parameters) -> Scope2OptimizationResult:
        """Solve Goal Programming model minimizing weighted deviations Z."""
        start_time = time.perf_counter()
        model = Scope2GoalModel(parameters).build()
        status = model.solve(self._build_solver())
        solve_duration = time.perf_counter() - start_time

        # A time-limited solve that still found a usable integer-feasible solution
        # reports "Not Solved" (optimality unproven) rather than "Optimal" -- that's an
        # acceptable, real answer (just not provably the best possible one), so it's
        # accepted here as long as the decision variables actually have values; only a
        # genuinely infeasible/undefined model is rejected.
        accepted_statuses = {"Optimal", "Not Solved"}
        if pulp.LpStatus[status] not in accepted_statuses:
            raise ValueError(f"Goal programming solve failed: {pulp.LpStatus[status]}")
        if pulp.value(model.variablesDict().get("d1_plus")) is None:
            raise ValueError(
                f"Goal programming solve hit its {self.time_limit_seconds}s time limit "
                "without finding any feasible solution. Try relaxing constraints "
                "(lower min pit stops, more tyre sets) or increasing the time limit."
            )

        lap_compounds = self._extract_lap_compounds(model, parameters)
        lap_compounds = self._normalize_to_valid_stints(lap_compounds, parameters)

        total_pit_stops = sum(
            pulp.value(model.variablesDict()[f"p_{lap}"])
            for lap in range(1, parameters.total_laps)
            if pulp.value(model.variablesDict()[f"p_{lap}"]) is not None
        )
        risk_score = self._compute_risk_score(lap_compounds, parameters)

        stints: List[StintPlan] = []
        current_compound = lap_compounds[1]
        stint_start = 1
        for lap in range(2, parameters.total_laps + 1):
            if lap_compounds[lap] != current_compound:
                stint_end = lap - 1
                stint_length = stint_end - stint_start + 1
                stint_time = self._stint_time(parameters, current_compound, stint_length)
                stints.append(
                    StintPlan(
                        stint_number=len(stints) + 1,
                        compound=TyreCompound(current_compound),
                        start_lap=stint_start,
                        end_lap=stint_end,
                        stint_length=stint_length,
                        predicted_stint_time=stint_time,
                    )
                )
                current_compound = lap_compounds[lap]
                stint_start = lap

        final_end = parameters.total_laps
        final_length = final_end - stint_start + 1
        final_time = self._stint_time(parameters, current_compound, final_length)
        stints.append(
            StintPlan(
                stint_number=len(stints) + 1,
                compound=TyreCompound(current_compound),
                start_lap=stint_start,
                end_lap=final_end,
                stint_length=final_length,
                predicted_stint_time=final_time,
            )
        )

        total_time = sum(stint.predicted_stint_time for stint in stints) + parameters.pit_loss_p * total_pit_stops

        deviations = GoalDeviations(
            d1_plus=float(pulp.value(model.variablesDict()["d1_plus"]) or 0.0),
            d1_minus=float(pulp.value(model.variablesDict()["d1_minus"]) or 0.0),
            d2_plus=float(pulp.value(model.variablesDict()["d2_plus"]) or 0.0),
            d2_minus=float(pulp.value(model.variablesDict()["d2_minus"]) or 0.0),
            d3_plus=float(pulp.value(model.variablesDict()["d3_plus"]) or 0.0),
            d3_minus=float(pulp.value(model.variablesDict()["d3_minus"]) or 0.0),
        )

        objective_value = (
            parameters.weights.weight_time_w1 * deviations.d1_plus
            + parameters.weights.weight_pit_stops_w2 * deviations.d2_plus
            + parameters.weights.weight_degradation_w3 * deviations.d3_plus
        )

        reported_status = "Optimal" if pulp.LpStatus[status] == "Optimal" else "Best found (time limit reached)"

        return Scope2OptimizationResult(
            balanced_race_time_seconds=total_time,
            time_delta_vs_fastest_seconds=total_time - parameters.targets.target_race_time_t_star,
            pit_stop_count=int(round(total_pit_stops)),
            optimal_pit_laps=[lap for lap in range(1, parameters.total_laps) if pulp.value(model.variablesDict()[f"p_{lap}"]) > 0.5],
            stints=stints,
            deviations=deviations,
            risk_score=risk_score,
            objective_value_z=objective_value,
            solver_status=reported_status,
            solve_duration_seconds=solve_duration,
        )

    @staticmethod
    def _compute_risk_score(lap_compounds: Dict[int, str], parameters: Scope2Parameters) -> float:
        """Recompute the strategy's total degradation-risk score from the final,
        normalized stint sequence. Tracks each compound's real tyre age lap by lap
        (resetting to 1 whenever the compound changes) and sums the risk-tier weight
        (0=low..3=very high) that age falls into, scaled to that compound's durability.

        This mirrors the MILP's age/tier logic but computed directly from the final
        lap-by-lap sequence rather than via decision variables, since the sequence is
        already fully determined at this point.
        """
        total_laps = parameters.total_laps
        total_risk = 0.0
        current_compound = None
        age = 0

        for lap in range(1, total_laps + 1):
            compound = lap_compounds.get(lap)
            if compound is None:
                continue
            age = age + 1 if compound == current_compound else 1
            current_compound = compound

            t1, t2, t3 = parameters.risk_tiers.get(
                compound, [max(1, total_laps // 3), max(2, total_laps * 2 // 3), max(3, total_laps * 9 // 10)]
            )
            if age <= t1:
                total_risk += 0
            elif age <= t2:
                total_risk += 1
            elif age <= t3:
                total_risk += 2
            else:
                total_risk += 3

        return total_risk
