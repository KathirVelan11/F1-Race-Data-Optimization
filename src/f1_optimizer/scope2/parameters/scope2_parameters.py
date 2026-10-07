"""Parameters container for Scope 2 Goal Programming."""
from typing import Dict, List
from pydantic import BaseModel, Field

from src.f1_optimizer.scope2.goals.goal_definitions import GoalTargets
from src.f1_optimizer.scope2.goals.weights import GoalWeights


class Scope2Parameters(BaseModel):
    """Encapsulates all parameters, targets, and weights needed for Model 2 (Goal Programming)."""
    total_laps: int = Field(..., description="Total race laps N")
    compounds: List[str] = Field(default_factory=lambda: ["SOFT", "MEDIUM", "HARD"])
    pit_loss_p: float = Field(default=13.0, description="Fixed pit loss P (s)")
    targets: GoalTargets = Field(..., description="Goal targets T*, P*, D*")
    weights: GoalWeights = Field(default_factory=GoalWeights, description="Priority weights w1, w2, w3")
    max_pit_stops: int = Field(default=2)
    min_stint_length: int = Field(default=5)
    max_stint_durability: Dict[str, int] = Field(default_factory=dict)
    predicted_lap_times: Dict[int, Dict[str, float]] = Field(default_factory=dict)
    compound_degradations: Dict[str, float] = Field(default_factory=dict)
