"""Parameters for Scope 1 MILP Tyre & Pit-Stop Strategy Model."""
from typing import Dict, List
from pydantic import BaseModel, Field


class Scope1Parameters(BaseModel):
    """Container for parameters required by Model 1 (MILP) as defined in PPT Slide 10.
    
    Sets:
        l in {1, ..., N} - laps
        c in {S, M, H} - tyre compounds
        
    Parameters:
        T_{l,c}: predicted lap time on compound c at current tyre age
        P: fixed pit-stop time loss (≈ 13 seconds)
        L_c^max: maximum durable stint length for compound c
        N: total race laps
    """
    total_laps: int = Field(..., description="Total race laps N")
    compounds: List[str] = Field(default_factory=lambda: ["SOFT", "MEDIUM", "HARD"])
    pit_loss_p: float = Field(default=13.0, description="Fixed pit-stop time loss P (≈ 13s)")
    max_pit_stops: int = Field(default=2, description="Max pit stops (constraint b: sum p_l <= 2)")
    min_stint_length: int = Field(default=5, description="Min stint length (constraint d: >= 5)")
    max_stint_durability: Dict[str, int] = Field(
        default_factory=lambda: {"SOFT": 25, "MEDIUM": 40, "HARD": 55},
        description="L_c^max maximum durable stint length for compound c"
    )
    predicted_lap_times: Dict[int, Dict[str, float]] = Field(
        default_factory=dict,
        description="T_{l,c} predicted lap times per lap and compound"
    )
