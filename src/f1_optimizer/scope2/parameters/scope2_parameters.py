"""Parameters container for Scope 2 Goal Programming."""
from typing import Dict, List
from pydantic import BaseModel, Field

from src.f1_optimizer.scope2.goals.goal_definitions import GoalTargets
from src.f1_optimizer.scope2.goals.weights import GoalWeights


class Scope2Parameters(BaseModel):
    """Encapsulates all parameters, targets, and weights needed for Model 2 (Goal Programming).

    All data-derived fields are required with no default -- see
    BackendOptimizationRunner.run_scope2 for how they're computed from real race data.
    `weights` is the one legitimate default: GoalWeights()'s 0.50/0.25/0.25 split is a
    real user-facing preference (not a stand-in for missing data), and it still passes
    GoalWeights' own strict sum-to-1 validation.
    """
    total_laps: int = Field(..., description="Total race laps N")
    compounds: List[str] = Field(..., description="Tyre compounds present in this race's data")
    pit_loss_p: float = Field(..., description="Pit-stop time loss P, derived from real race/circuit data")
    targets: GoalTargets = Field(..., description="Goal targets T*, P*, D*")
    weights: GoalWeights = Field(default_factory=GoalWeights, description="Priority weights w1, w2, w3")
    max_pit_stops: int = Field(..., description="Max pit stops, derived from real data or user input")
    min_stint_length: int = Field(..., description="Min stint length, derived from real data or user input")
    max_stint_durability: Dict[str, int] = Field(
        ..., description="L_c^max maximum durable stint length for compound c, derived from real tyre-life data"
    )
    predicted_lap_times: Dict[int, Dict[str, float]] = Field(
        ..., description="T_{l,c} predicted lap times per lap and compound"
    )
    compound_degradations: Dict[str, float] = Field(
        ..., description="Relative degradation severity per compound, 0 (longest-lasting) to 1 (fastest-wearing)"
    )
