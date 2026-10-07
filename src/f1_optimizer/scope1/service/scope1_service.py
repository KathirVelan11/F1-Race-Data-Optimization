"""Scope 1 end-to-end service coordinating parameter extraction, modeling, and solving."""
from typing import Optional

from src.f1_optimizer.common.race.race_context import RaceContext
from src.f1_optimizer.scope1.output.scope1_result import Scope1OptimizationResult
from src.f1_optimizer.scope1.parameters.scope1_parameters import Scope1Parameters
from src.f1_optimizer.scope1.solver.milp_solver import Scope1MilpSolver


class Scope1Service:
    """Service layer for Scope 1: builds parameters from race context and solves MILP."""

    def __init__(self, solver: Optional[Scope1MilpSolver] = None):
        self.solver = solver or Scope1MilpSolver()

    def run_optimization(self, race_context: RaceContext) -> Scope1OptimizationResult:
        """Extract parameters from RaceContext, build the MILP, solve, and return the result."""
        compounds = list(race_context.available_compounds or ["SOFT", "MEDIUM", "HARD"])
        predicted_lap_times: dict[int, dict[str, float]] = {}

        for lap in range(1, race_context.total_laps + 1):
            predicted_lap_times[lap] = {}
            for compound in compounds:
                base_time = race_context.compound_base_times.get(compound, 90.0)
                degradation = race_context.compound_degradation_slopes.get(compound, 0.03)
                predicted_lap_times[lap][compound] = base_time + degradation * lap

        parameters = {
            "total_laps": race_context.total_laps,
            "compounds": compounds,
            "pit_loss_p": race_context.pit_loss_seconds,
            "max_pit_stops": 2,
            "min_stint_length": 5,
            "max_stint_durability": race_context.compound_durability_limits or {compound: 30 for compound in compounds},
            "predicted_lap_times": predicted_lap_times,
        }

        scope1_parameters = Scope1Parameters(**parameters)
        return self.solver.solve(scope1_parameters)
