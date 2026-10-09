"""Solver interface and execution for Scope 1 MILP model."""
import time
from typing import Any, Dict, List

import pulp

from src.f1_optimizer.common.schemas.race import TyreCompound
from src.f1_optimizer.common.schemas.strategy import StintPlan
from src.f1_optimizer.scope1.model.milp_model import Scope1MilpModel
from src.f1_optimizer.scope1.output.scope1_result import Scope1OptimizationResult
from src.f1_optimizer.scope1.parameters.scope1_parameters import Scope1Parameters


class Scope1MilpSolver:
    """Invokes the MILP solver (e.g. PuLP with CBC/HiGHS) to solve Model 1."""

    def __init__(self, solver_name: str = "HiGHS", time_limit_seconds: int = 20):
        """`solver_name` selects the backend ("HiGHS" or "PULP_CBC_CMD"); HiGHS is the
        default since it's free and noticeably faster than CBC in practice. Model 1
        usually solves in well under a second regardless, but the time limit is applied
        for consistency with Scope2GoalSolver."""
        self.solver_name = solver_name
        self.time_limit_seconds = time_limit_seconds

    def _build_solver(self) -> Any:
        if self.solver_name == "HiGHS":
            return pulp.HiGHS(msg=False, timeLimit=self.time_limit_seconds)
        return pulp.PULP_CBC_CMD(msg=False, timeLimit=self.time_limit_seconds)

    def _extract_lap_compounds(self, model: Any, parameters: Scope1Parameters) -> Dict[int, str]:
        """Extract the chosen compound for each lap from the solved model."""
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
    def _stint_time(parameters: Scope1Parameters, compound: str, stint_length: int) -> float:
        """True predicted time for a stint of this compound and length, using tyre age
        1..stint_length (NOT race-lap number) -- sum_{age=1}^{len} (base + rate*age)."""
        base = parameters.compound_base_pace.get(compound, 0.0)
        rate = parameters.compound_degradation_rate.get(compound, 0.0)
        return stint_length * base + rate * (stint_length * (stint_length + 1) / 2)

    def _normalize_to_valid_stints(
        self,
        lap_compounds: Dict[int, str],
        parameters: Scope1Parameters,
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
                normalized[lap] = lap_compounds.get(lap, "SOFT")

        return normalized

    def solve(self, parameters: Scope1Parameters) -> Scope1OptimizationResult:
        """Solve the MILP model for the given parameters and return structured result."""
        start_time = time.perf_counter()
        model = Scope1MilpModel(parameters).build()
        status = model.solve(self._build_solver())
        solve_duration = time.perf_counter() - start_time

        accepted_statuses = {"Optimal", "Not Solved"}
        if pulp.LpStatus[status] not in accepted_statuses:
            raise ValueError(f"MILP could not find an optimal solution: {pulp.LpStatus[status]}")
        if pulp.value(model.variablesDict().get(f"x_1_{parameters.compounds[0]}")) is None:
            raise ValueError(
                f"MILP solve hit its {self.time_limit_seconds}s time limit without finding "
                "any feasible solution. Try relaxing constraints (lower min pit stops, "
                "more tyre sets) or increasing the time limit."
            )

        lap_compounds = self._extract_lap_compounds(model, parameters)
        lap_compounds = self._normalize_to_valid_stints(lap_compounds, parameters)

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

        optimal_pit_laps = []
        for idx in range(1, len(stints)):
            optimal_pit_laps.append(stints[idx].start_lap - 1)

        total_race_time = (
            sum(stint.predicted_stint_time for stint in stints)
            + parameters.pit_loss_p * len(optimal_pit_laps)
        )

        reported_status = "Optimal" if pulp.LpStatus[status] == "Optimal" else "Best found (time limit reached)"

        return Scope1OptimizationResult(
            minimum_predicted_race_time=total_race_time,
            optimal_pit_laps=optimal_pit_laps,
            pit_stop_count=len(optimal_pit_laps),
            stints=stints,
            lap_compounds=lap_compounds,
            solver_status=reported_status,
            solve_duration_seconds=solve_duration,
        )
