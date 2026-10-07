"""Result data structures for Scope 1 MILP optimization."""
from typing import List, Dict
from pydantic import BaseModel, Field

from src.f1_optimizer.common.schemas.strategy import StintPlan, StrategyResult


class Scope1OptimizationResult(BaseModel):
    """Specific result output for Scope 1 MILP optimization.
    
    Contains:
        - Optimal pit-stop laps
        - Tyre compound used in each stint
        - Minimum predicted race time (T*)
        - Lap-by-lap compound assignment x_{l,c}
        - Pit decision vector p_l
    """
    minimum_predicted_race_time: float = Field(..., description="Fastest achievable race time T* (seconds)")
    optimal_pit_laps: List[int] = Field(default_factory=list, description="Laps after which a pit stop occurs")
    pit_stop_count: int = Field(..., description="Total pit stops")
    stints: List[StintPlan] = Field(default_factory=list, description="Tyre stints with start/end and compound")
    lap_compounds: Dict[int, str] = Field(default_factory=dict, description="Lap l -> selected compound c")
    solver_status: str = Field(..., description="Solver exit status (OPTIMAL, INFEASIBLE, etc.)")
    solve_duration_seconds: float = Field(..., description="Time taken by the solver in seconds")

    def to_generic_strategy_result(self) -> StrategyResult:
        """Convert to common generic StrategyResult."""
        return StrategyResult(
            model_name="Scope 1 (MILP - Fastest Strategy)",
            total_race_time_seconds=self.minimum_predicted_race_time,
            total_pit_stops=self.pit_stop_count,
            pit_laps=self.optimal_pit_laps,
            stints=self.stints,
            solver_status=self.solver_status,
            execution_time_seconds=self.solve_duration_seconds,
            notes="Single fastest strategy minimizing race time."
        )
