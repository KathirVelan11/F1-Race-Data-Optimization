"""Tyre degradation estimation and curve-fitting models."""
from typing import Tuple
import numpy as np
import pandas as pd

from src.f1_optimizer.common.utils.time_utils import lap_time_str_to_seconds


class TyreDegradationModel:
    """Estimates empirical tyre degradation slopes and baseline lap times per compound."""

    def fit_compound_degradation(
        self,
        race_df: pd.DataFrame,
        compound: str
    ) -> Tuple[float, float]:
        """Fit degradation slope and base lap time for a specific tyre compound, from real
        lap-time data only.

        Fits an ordinary-least-squares line (lap_time = intercept + slope * tyre_age) across
        every lap on this compound, using the real per-lap tyre-age column (TyreLife) when the
        data provides one. This uses every lap as evidence, unlike a two-point estimate, so a
        single outlier lap (safety car, traffic, pit in/out) can't single-handedly dictate the
        slope the way it would if only the min/max laps were used.

        Returns:
            (base_lap_time, degradation_rate_per_lap)
            base_lap_time is the fitted intercept (predicted pace at tyre_age=0).
            degradation_rate_per_lap is the fitted slope, floored at 0.0 (a tyre is never
            modeled as getting faster with age).

        Raises:
            ValueError: if race_df has no usable data for this compound. There is no sane
            universal fallback for a compound's pace/degradation -- returning a fabricated
            number here would silently corrupt the caller's model instead of surfacing
            that this compound has no real data to learn from.
        """
        if race_df is None or race_df.empty:
            raise ValueError("race_df is empty; cannot fit degradation without race data.")

        compound_column = None
        for name in ["Compound", "compound", "TyreCompound"]:
            if name in race_df.columns:
                compound_column = name
                break

        if compound_column is None:
            raise ValueError("race_df has no Compound/TyreCompound column.")

        subset = race_df[race_df[compound_column].astype(str).str.upper() == str(compound).upper()]
        if subset.empty:
            raise ValueError(f"No rows for compound {compound!r} in race_df.")

        lap_times = subset["LapTime"] if "LapTime" in subset.columns else subset.iloc[:, 0]
        numeric_times = pd.Series(
            [lap_time_str_to_seconds(str(value)) for value in lap_times]
        )

        age_column = None
        for name in ["TyreLife", "tyre_age", "TyreAge"]:
            if name in subset.columns:
                age_column = name
                break

        if age_column is not None:
            ages = pd.to_numeric(subset[age_column], errors="coerce")
        else:
            # No real per-lap tyre-age column available -- fall back to lap order within
            # this compound's rows as a proxy for age (1, 2, 3, ... in data order).
            ages = pd.Series(range(1, len(subset) + 1), index=subset.index, dtype=float)

        valid = pd.DataFrame({"age": ages.values, "lap_time": numeric_times.values}).dropna()

        if valid.empty:
            raise ValueError(f"No numeric LapTime values for compound {compound!r} in race_df.")

        if len(valid) == 1 or valid["age"].nunique() == 1:
            # Can't fit a line through a single point / a single distinct age -- the only
            # honest estimate is "no measured degradation", with pace as the observed median.
            base_lap_time = float(valid["lap_time"].median())
            degradation_rate = 0.0
            return base_lap_time, degradation_rate

        slope, intercept = np.polyfit(valid["age"].to_numpy(), valid["lap_time"].to_numpy(), 1)

        base_lap_time = float(intercept)
        degradation_rate = max(float(slope), 0.0)
        return base_lap_time, degradation_rate

    def predict_lap_time(
        self,
        base_lap_time: float,
        degradation_rate: float,
        tyre_age: int
    ) -> float:
        """Predict lap time at a specific tyre age."""
        return float(base_lap_time + max(0.0, degradation_rate) * max(0, int(tyre_age)))
