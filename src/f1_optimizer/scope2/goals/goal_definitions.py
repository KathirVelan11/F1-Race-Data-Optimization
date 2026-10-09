"""Goal target definitions and deviation representations for Goal Programming."""
from pydantic import BaseModel, Field


class GoalTargets(BaseModel):
    """Target values (T*, P*, R*) for Scope 2 Model.

    Goals:
        Goal 1 (Time):        T + d1- - d1+ = T*   (fastest time, from Scope 1)
        Goal 2 (Pit stops):   P + d2- - d2+ = P*   (user's max acceptable pit stop count --
                                                      see BackendOptimizationRunner.run_scope2)
        Goal 3 (Risk):        R + d3- - d3+ = R*   (target cumulative degradation-risk
                                                      score: sum over laps of each lap's
                                                      risk tier weight, 0=low..3=very high,
                                                      scaled to each compound's real
                                                      durability -- see
                                                      BackendOptimizationRunner._get_degradation_risk_tiers)

    All three targets are "best achievable," not arbitrary or historical values -- each
    is the real solved optimum of its own goal in isolation, under this race's actual
    constraints (min/max pit stops, min stint length, tyre-set/durability/risk-ceiling
    limits):
        T* = Model 1's solved fastest race time.
        P* = the user's max_pit_stops input directly (the ceiling they already chose is
             also what Goal 2 treats as "on target" -- there's no separate historical
             pit-count estimate anymore).
        R* = the true minimum total risk score achievable for this race (from a
             dedicated minimize-risk solve -- see
             BackendOptimizationRunner._get_min_achievable_risk_score). Not a fixed 0:
             a tyre cannot physically stay in the lowest risk tier for a whole stint, so
             an unreachable R*=0 would leave every strategy with the same unavoidable
             d3+ floor and no real pressure to minimize risk further. Using the true
             achievable floor instead means d3+=0 is reachable by the best strategy
             (mirrors how T* already works for Model 1), and Goal 3 keeps pushing toward
             fresher tyres above that floor.
    """
    target_race_time_t_star: float = Field(..., description="T*: Fastest achievable race time from Scope 1 (s)")
    target_pit_stops_p_star: int = Field(default=1, description="P*: User's max_pit_stops input")
    target_degradation_d_star: float = Field(
        default=0.0,
        description="R*: True minimum achievable degradation-risk score for this race (see class docstring)",
    )


class GoalDeviations(BaseModel):
    """Under- and over-achievement deviations for each goal."""
    d1_plus: float = Field(default=0.0, description="Over-achievement of race time (time penalty)")
    d1_minus: float = Field(default=0.0, description="Under-achievement of race time")
    d2_plus: float = Field(default=0.0, description="Over-achievement of pit stops")
    d2_minus: float = Field(default=0.0, description="Under-achievement of pit stops")
    d3_plus: float = Field(default=0.0, description="Over-achievement of degradation")
    d3_minus: float = Field(default=0.0, description="Under-achievement of degradation")
