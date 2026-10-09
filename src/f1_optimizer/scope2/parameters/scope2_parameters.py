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
    min_pit_stops: int = Field(..., description="Min pit stops, derived from real data or user input")
    max_pit_stops: int = Field(
        ...,
        description=(
            "Max pit stops, from user input (see BackendOptimizationRunner.run_scope2). "
            "Enforced as a genuine hard ceiling in Scope2GoalModel (Model 2 only -- Model "
            "1/MILP has no pit-stop ceiling). Also used directly as Goal 2's target P*."
        ),
    )
    min_stint_length: int = Field(..., description="Min stint length, derived from real data or user input")
    max_stint_durability: Dict[str, int] = Field(
        ..., description="L_c^max maximum durable stint length for compound c, derived from real tyre-life data"
    )
    max_sets_per_compound: Dict[str, int] = Field(
        ..., description="Max number of separate stints allowed on each compound (tyre-set allocation limit)"
    )
    predicted_lap_times: Dict[int, Dict[str, float]] = Field(
        ...,
        description=(
            "T_{l,c} predicted lap times per lap and compound, AT TYRE AGE = l (i.e. as if "
            "that compound had been fitted at the start of the race). Not used by the "
            "objective itself -- see compound_base_pace/compound_degradation_rate, which "
            "combine with the model's own true per-stint age[l,c] variable instead."
        ),
    )
    compound_base_pace: Dict[str, float] = Field(
        ..., description="alpha_c: fitted base lap time (tyre age 0) per compound, from real data"
    )
    compound_degradation_rate: Dict[str, float] = Field(
        ..., description="beta_c: fitted degradation rate (seconds/lap of tyre age) per compound, from real data"
    )
    risk_tiers: Dict[str, List[int]] = Field(
        ...,
        description=(
            "Per-compound tyre-age thresholds [t1,t2,t3] for the 4 degradation-risk tiers "
            "(0=low age<=t1, 1=moderate age<=t2, 2=high age<=t3, 3=very high age>t3), "
            "scaled to that compound's own real durability."
        ),
    )
    max_risk_tier_per_compound: Dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Optional per-compound hard ceiling on degradation-risk tier (0=low, "
            "1=moderate, 2=high, 3=very high). A compound present here can never be run "
            "into an age beyond the given tier, regardless of goal weights. A compound "
            "absent from this dict has no ceiling (full durability range allowed)."
        ),
    )
