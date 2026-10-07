"""Pydantic schemas for race entities, drivers, and laps."""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TyreCompound(str, Enum):
    """F1 Tyre Compounds."""
    SOFT = "SOFT"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    INTERMEDIATE = "INTERMEDIATE"
    WET = "WET"
    # Legacy compounds from 2018
    ULTRASOFT = "ULTRASOFT"
    SUPERSOFT = "SUPERSOFT"
    HYPERSOFT = "HYPERSOFT"


class LapRecord(BaseModel):
    """Single lap record in the dataset."""
    race_id: int
    year: int
    race_name: str
    driver_code: str
    team_name: str
    lap_number: int
    lap_time_str: str
    lap_time_seconds: Optional[float] = None
    position: int
    compound: TyreCompound
    tyre_life: float
    stint: float
    pit_duration: Optional[float] = None


class RaceSummary(BaseModel):
    """Summary of a Grand Prix event."""
    race_id: int
    year: int
    race_name: str
    total_laps: int
    driver_count: int
