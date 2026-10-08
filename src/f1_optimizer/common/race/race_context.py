"""Race context abstraction aggregating race parameters, compounds, and lap totals."""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class RaceContext(BaseModel):
    """Encapsulates all race-specific constants and parameters needed for optimization.

    `available_compounds` and `pit_loss_seconds` have no default: the compound set and
    pit cost must be derived from the selected race's real data (which compounds it
    actually used, and its real recorded pit-stop durations) by whoever builds this
    context, not assumed to always be a fixed SOFT/MEDIUM/HARD set at a flat cost.
    """
    race_id: int
    year: int
    race_name: str
    driver_code: Optional[str] = None
    total_laps: int
    available_compounds: List[str] = Field(..., description="Compounds present in this race's real data")
    pit_loss_seconds: float = Field(..., description="Pit-stop time loss derived from real race/circuit data")
    compound_base_times: Dict[str, float] = Field(default_factory=dict)
    compound_degradation_slopes: Dict[str, float] = Field(default_factory=dict)
    compound_durability_limits: Dict[str, int] = Field(default_factory=dict)
