"""Parameters for Scope 1 MILP Tyre & Pit-Stop Strategy Model."""
from typing import Dict, List
from pydantic import BaseModel, Field


class Scope1Parameters(BaseModel):
    """Container for parameters required by Model 1 (MILP).

    Sets:
        l in {1, ..., N} - laps
        c in C - tyre compounds actually present in the selected race's data

    Parameters:
        T_{l,c}: predicted lap time on compound c at current tyre age
        P: pit-stop time loss, derived from real per-race/circuit pit data
        L_c^max: maximum durable stint length for compound c
        N: total race laps

    Every field below is required with no default: all values must be derived from
    real race data by the caller (see BackendOptimizationRunner._build_scope1_parameters).
    There is no sane universal fallback for these -- a hardcoded default here would
    silently mask missing data instead of failing loudly.
    """
    total_laps: int = Field(..., description="Total race laps N")
    compounds: List[str] = Field(..., description="Tyre compounds present in this race's data")
    pit_loss_p: float = Field(..., description="Pit-stop time loss P, derived from real race/circuit data")
    min_pit_stops: int = Field(..., description="Min pit stops (constraint b: sum p_l >= min_pit_stops)")
    min_stint_length: int = Field(..., description="Min stint length (constraint d)")
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
            "that compound had been fitted at the start of the race). Used only for "
            "pre-solve tie-breaking and legacy display; the MILP objective itself uses "
            "compound_base_pace/compound_degradation_rate with the true per-stint tyre-age "
            "variable so it is not fooled by this lap-indexed approximation."
        ),
    )
    compound_base_pace: Dict[str, float] = Field(
        ..., description="alpha_c: fitted base lap time (tyre age 0) per compound, from real data"
    )
    compound_degradation_rate: Dict[str, float] = Field(
        ..., description="beta_c: fitted degradation rate (seconds/lap of tyre age) per compound, from real data"
    )
