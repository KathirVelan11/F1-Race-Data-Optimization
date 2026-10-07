"""Request and response schemas for FastAPI endpoints."""
from typing import List, Optional
from pydantic import BaseModel, Field

from src.f1_optimizer.scope2.goals.weights import GoalWeights


class OptimizeScope1Request(BaseModel):
    """Request payload to execute Scope 1 MILP optimization."""
    year: int
    race_name: str
    driver_code: Optional[str] = None
    pit_loss_p: Optional[float] = 13.0
    max_pit_stops: Optional[int] = 2


class OptimizeScope2Request(BaseModel):
    """Request payload to execute Scope 2 Goal Programming optimization."""
    year: int
    race_name: str
    driver_code: Optional[str] = None
    pit_loss_p: Optional[float] = 13.0
    target_race_time_t_star: Optional[float] = None
    target_pit_stops_p_star: Optional[int] = 1
    target_degradation_d_star: Optional[float] = 0.05
    weights: GoalWeights = Field(default_factory=GoalWeights)


class CompareStrategiesRequest(BaseModel):
    """Request payload to compare Scope 1 and Scope 2."""
    year: int
    race_name: str
    driver_code: Optional[str] = None
    pit_loss_p: Optional[float] = 13.0
    weights: GoalWeights = Field(default_factory=GoalWeights)
