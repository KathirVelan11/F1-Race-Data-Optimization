"""Race context abstraction aggregating race parameters, compounds, and lap totals."""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class RaceContext(BaseModel):
    """Encapsulates all race-specific constants and parameters needed for optimization."""
    race_id: int
    year: int
    race_name: str
    driver_code: Optional[str] = None
    total_laps: int
    available_compounds: List[str] = Field(default_factory=lambda: ["SOFT", "MEDIUM", "HARD"])
    pit_loss_seconds: float = 13.0
    compound_base_times: Dict[str, float] = Field(default_factory=dict)
    compound_degradation_slopes: Dict[str, float] = Field(default_factory=dict)
    compound_durability_limits: Dict[str, int] = Field(default_factory=dict)
