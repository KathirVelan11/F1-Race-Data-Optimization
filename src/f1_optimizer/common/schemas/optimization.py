"""Schemas for optimization status and parameters."""
from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel, Field


class SolverStatus(str, Enum):
    """Solver outcome state."""
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNBOUNDED = "UNBOUNDED"
    ERROR = "ERROR"


class BaseOptimizationParameters(BaseModel):
    """Base optimization parameters common across models."""
    total_laps: int
    pit_loss_seconds: float = 13.0
    max_pit_stops: int = 2
    min_stint_length: int = 5
    compound_durability_limits: Dict[str, int] = Field(
        default_factory=lambda: {"SOFT": 25, "MEDIUM": 40, "HARD": 55}
    )
