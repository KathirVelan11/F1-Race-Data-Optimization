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

    def __init__(self, solver_name: str = "PULP_CBC_CMD"):
        self.solver_name = solver_name

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
                best_compound = min(
                    parameters.compounds,
                    key=lambda item: parameters.predicted_lap_times.get(lap, {}).get(item, float("inf")),
                )
            lap_compounds[lap] = best_compound
        return lap_compounds

    def solve(self, parameters: Scope2Parameters) -> Scope2OptimizationResult:
        """Solve Goal Programming model minimizing weighted deviations Z."""
        start_time = time.perf_counter()
        model = Scope2GoalModel(parameters).build()
        status = model.solve(pulp.PULP_CBC_CMD(msg=False))
        solve_duration = time.perf_counter() - start_time

        if pulp.LpStatus[status] not in {"Optimal", "Not Solved"}:
            raise ValueError(f"Goal programming solve failed: {pulp.LpStatus[status]}")

        lap_compounds = self._extract_lap_compounds(model, parameters)

        total_time = sum(
            parameters.predicted_lap_times.get(lap, {}).get(compound, 0.0)
            for lap, compound in lap_compounds.items()
        )
        total_pit_stops = sum(
            pulp.value(model.variablesDict()[f"p_{lap}"])
            for lap in range(1, parameters.total_laps)
            if pulp.value(model.variablesDict()[f"p_{lap}"]) is not None
        )
        degradation_index = sum(
            parameters.compound_degradations.get(compound, 0.0) for _, compound in lap_compounds.items()
        ) / parameters.total_laps

        stints: List[StintPlan] = []
        current_compound = lap_compounds[1]
        stint_start = 1
        for lap in range(2, parameters.total_laps + 1):
            if lap_compounds[lap] != current_compound:
                stint_end = lap - 1
                stint_length = stint_end - stint_start + 1
                stint_time = sum(
                    parameters.predicted_lap_times.get(lap_idx, {}).get(current_compound, 0.0)
                    for lap_idx in range(stint_start, stint_end + 1)
                )
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
        final_time = sum(
            parameters.predicted_lap_times.get(lap_idx, {}).get(current_compound, 0.0)
            for lap_idx in range(stint_start, final_end + 1)
        )
        stints.append(
            StintPlan(
                stint_number=len(stints) + 1,
                compound=TyreCompound(current_compound),
                start_lap=stint_start,
                end_lap=final_end,
                stint_length=final_end - stint_start + 1,
                predicted_stint_time=final_time,
            )
        )

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

        return Scope2OptimizationResult(
            balanced_race_time_seconds=total_time,
            time_delta_vs_fastest_seconds=total_time - parameters.targets.target_race_time_t_star,
            pit_stop_count=int(round(total_pit_stops)),
            optimal_pit_laps=[lap for lap in range(1, parameters.total_laps) if pulp.value(model.variablesDict()[f"p_{lap}"]) > 0.5],
            stints=stints,
            deviations=deviations,
            objective_value_z=objective_value,
            solver_status=pulp.LpStatus[status],
            solve_duration_seconds=solve_duration,
        )
