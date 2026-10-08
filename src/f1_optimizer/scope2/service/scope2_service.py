"""Scope 2 service coordinating goal definitions, parameters, and Goal Programming solve."""
from typing import Optional

from src.f1_optimizer.common.race.race_context import RaceContext
from src.f1_optimizer.scope2.goals.goal_definitions import GoalTargets
from src.f1_optimizer.scope2.goals.weights import GoalWeights
from src.f1_optimizer.scope2.output.scope2_result import Scope2OptimizationResult
from src.f1_optimizer.scope2.parameters.scope2_parameters import Scope2Parameters
from src.f1_optimizer.scope2.solver.goal_solver import Scope2GoalSolver


class Scope2Service:
    """Service layer for Scope 2: prepares multi-objective targets and solves Goal Program."""

    def __init__(self, solver: Optional[Scope2GoalSolver] = None):
        self.solver = solver or Scope2GoalSolver()

    def run_optimization(
        self,
        race_context: RaceContext,
        target_race_time_t_star: float,
        target_pit_stops_p_star: int,
        target_degradation_d_star: float,
        weights: GoalWeights,
        max_pit_stops: int,
        min_stint_length: int,
    ) -> Scope2OptimizationResult:
        """Run Goal Programming using reference T* from Scope 1 and team priority weights.

        `max_pit_stops` / `min_stint_length` must be resolved by the caller from real race
        data, same as Scope1Service -- no default here, since this service has no race
        data of its own to derive a sane value from.
        """
        params = Scope2Parameters(
            total_laps=race_context.total_laps,
            compounds=race_context.available_compounds,
            pit_loss_p=race_context.pit_loss_seconds,
            targets=GoalTargets(
                target_race_time_t_star=target_race_time_t_star,
                target_pit_stops_p_star=target_pit_stops_p_star,
                target_degradation_d_star=target_degradation_d_star,
            ),
            weights=weights,
            max_pit_stops=max_pit_stops,
            min_stint_length=min_stint_length,
            max_stint_durability=race_context.compound_durability_limits,
            predicted_lap_times={
                lap: {
                    compound: (race_context.compound_base_times[compound]
                              + race_context.compound_degradation_slopes[compound] * lap)
                    for compound in race_context.available_compounds
                }
                for lap in range(1, race_context.total_laps + 1)
            },
            compound_degradations=race_context.compound_degradation_slopes,
        )
        return self.solver.solve(params)
