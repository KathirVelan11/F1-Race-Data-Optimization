"""Result structures for Scope 2 Goal Programming optimization."""
from typing import List, Dict
from pydantic import BaseModel, Field

from src.f1_optimizer.common.schemas.strategy import StintPlan, StrategyResult
from src.f1_optimizer.scope2.goals.goal_definitions import GoalDeviations


class Scope2OptimizationResult(BaseModel):
    """Specific result output for Scope 2 Goal Programming optimization.
    
    Contains:
        - Balanced race time
        - Time deviation from fastest (T - T*)
        - Pit stop count and optimal laps
        - Stint breakdown
        - Final goal deviations d1+, d2+, d3+
        - Comparison metrics vs Scope 1
    """
    balanced_race_time_seconds: float = Field(..., description="Achieved race time under balanced priorities")
    time_delta_vs_fastest_seconds: float = Field(..., description="Time penalty / trade-off (T - T*)")
    pit_stop_count: int = Field(..., description="Balanced pit stop count")
    optimal_pit_laps: List[int] = Field(default_factory=list, description="Laps after which pit stop occurs")
    stints: List[StintPlan] = Field(default_factory=list, description="Tyre stints with compound and length")
    deviations: GoalDeviations = Field(..., description="Achieved deviation variables")
    risk_score: float = Field(..., description="Total degradation-risk score for this strategy (sum of per-lap risk-tier weights, 0=low..3=very high)")
    objective_value_z: float = Field(..., description="Weighted penalty objective value Z")
    solver_status: str = Field(..., description="Solver exit status")
    solve_duration_seconds: float = Field(..., description="Solve duration in seconds")

    def to_generic_strategy_result(self) -> StrategyResult:
        """Convert to common generic StrategyResult."""
        return StrategyResult(
            model_name="Scope 2 (Goal Programming - Balanced Strategy)",
            total_race_time_seconds=self.balanced_race_time_seconds,
            total_pit_stops=self.pit_stop_count,
            pit_laps=self.optimal_pit_laps,
            stints=self.stints,
            solver_status=self.solver_status,
            execution_time_seconds=self.solve_duration_seconds,
            notes=f"Balanced multi-objective strategy with delta +{self.time_delta_vs_fastest_seconds:.2f}s."
        )
