"""Scope 1 end-to-end service coordinating parameter extraction, modeling, and solving."""
from typing import Dict, Optional

from src.f1_optimizer.common.race.race_context import RaceContext
from src.f1_optimizer.scope1.output.scope1_result import Scope1OptimizationResult
from src.f1_optimizer.scope1.parameters.scope1_parameters import Scope1Parameters
from src.f1_optimizer.scope1.solver.milp_solver import Scope1MilpSolver


class Scope1Service:
    """Service layer for Scope 1: builds parameters from race context and solves MILP."""

    def __init__(self, solver: Optional[Scope1MilpSolver] = None):
        self.solver = solver or Scope1MilpSolver()

    def run_optimization(
        self,
        race_context: RaceContext,
        min_pit_stops: int,
        min_stint_length: int,
        max_sets_per_compound: Dict[str, int],
    ) -> Scope1OptimizationResult:
        """Extract parameters from RaceContext, build the MILP, solve, and return the result.

        `min_pit_stops` / `min_stint_length` / `max_sets_per_compound` must be resolved by
        the caller from real race data (see BackendOptimizationRunner) -- this service has
        no race data of its own to derive a sane value from, so it takes no default.
        """
        compounds = list(race_context.available_compounds)
        predicted_lap_times: dict[int, dict[str, float]] = {}

        for lap in range(1, race_context.total_laps + 1):
            predicted_lap_times[lap] = {}
            for compound in compounds:
                base_time = race_context.compound_base_times[compound]
                degradation = race_context.compound_degradation_slopes[compound]
                predicted_lap_times[lap][compound] = base_time + degradation * lap

        parameters = {
            "total_laps": race_context.total_laps,
            "compounds": compounds,
            "pit_loss_p": race_context.pit_loss_seconds,
            "min_pit_stops": min_pit_stops,
            "min_stint_length": min_stint_length,
            "max_stint_durability": race_context.compound_durability_limits,
            "max_sets_per_compound": max_sets_per_compound,
            "predicted_lap_times": predicted_lap_times,
        }

        scope1_parameters = Scope1Parameters(**parameters)
        return self.solver.solve(scope1_parameters)
