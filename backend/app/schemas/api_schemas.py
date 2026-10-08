"""Request schemas for FastAPI endpoints.

These intentionally carry no race-data-derived defaults (pit loss, durability, etc.) --
those are always computed server-side from the selected race's real data in
BackendOptimizationRunner. `weights` is the one legitimate default: GoalWeights()'s
0.50/0.25/0.25 split is a real user-facing preference, not a stand-in for missing data,
and it enforces its own strict sum-to-1 validation.

Field names match exactly what the frontend sends to /api/scope1/optimize,
/api/scope2/optimize, and /api/compare (see frontend/src/App.tsx).
"""
from typing import Dict, Optional
from pydantic import BaseModel, Field

from src.f1_optimizer.scope2.goals.weights import GoalWeights


class OptimizeScope1Request(BaseModel):
    """Request payload to execute Scope 1 MILP optimization."""
    year: int
    race_name: str
    driver_code: Optional[str] = None
    min_pit_stops: Optional[int] = None
    min_stint_length: Optional[int] = None
    max_sets_per_compound: Optional[Dict[str, int]] = None


class OptimizeScope2Request(BaseModel):
    """Request payload to execute Scope 2 Goal Programming optimization."""
    year: int
    race_name: str
    driver_code: Optional[str] = None
    min_pit_stops: Optional[int] = None
    min_stint_length: Optional[int] = None
    max_sets_per_compound: Optional[Dict[str, int]] = None
    weights: GoalWeights = Field(default_factory=GoalWeights)


class CompareStrategiesRequest(BaseModel):
    """Request payload to compare Scope 1 and Scope 2 (the /api/compare endpoint the
    frontend actually calls)."""
    year: int
    race_name: str
    driver_code: Optional[str] = None
    min_pit_stops: Optional[int] = None
    min_stint_length: Optional[int] = None
    max_sets_per_compound: Optional[Dict[str, int]] = None
    weights: GoalWeights = Field(default_factory=GoalWeights)
