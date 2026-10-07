"""Goal target definitions and deviation representations for Goal Programming."""
from pydantic import BaseModel, Field


class GoalTargets(BaseModel):
    """Target values (T*, P*, D*) for Scope 2 Model as defined in PPT Slide 13.
    
    Goals:
        Goal 1 (Time):        T + d1- - d1+ = T*   (fastest time, from Scope 1)
        Goal 2 (Pit stops):   P + d2- - d2+ = P*   (e.g., target pit stop count)
        Goal 3 (Degradation): D + d3- - d3+ = D*   (target degradation rate)
    """
    target_race_time_t_star: float = Field(..., description="T*: Fastest achievable race time from Scope 1 (s)")
    target_pit_stops_p_star: int = Field(default=1, description="P*: Target pit stop count")
    target_degradation_d_star: float = Field(default=0.05, description="D*: Target degradation rate (s/lap)")


class GoalDeviations(BaseModel):
    """Under- and over-achievement deviations for each goal."""
    d1_plus: float = Field(default=0.0, description="Over-achievement of race time (time penalty)")
    d1_minus: float = Field(default=0.0, description="Under-achievement of race time")
    d2_plus: float = Field(default=0.0, description="Over-achievement of pit stops")
    d2_minus: float = Field(default=0.0, description="Under-achievement of pit stops")
    d3_plus: float = Field(default=0.0, description="Over-achievement of degradation")
    d3_minus: float = Field(default=0.0, description="Under-achievement of degradation")
