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
    """Base optimization parameters common across models.

    No defaults: every field must be derived from the selected race's real data by the
    caller, so a missing value fails loudly instead of silently falling back to a
    stale constant.
    """
    total_laps: int
    pit_loss_seconds: float = Field(..., description="Pit-stop time loss derived from real race/circuit data")
    max_pit_stops: int = Field(..., description="Max pit stops, derived from real data or user input")
    min_stint_length: int = Field(..., description="Min stint length, derived from real data or user input")
    compound_durability_limits: Dict[str, int] = Field(
        ..., description="Max durable stint length per compound, derived from real tyre-life data"
    )
