"""Tyre degradation estimation and curve-fitting models."""
from typing import Tuple
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

        Returns:
            (base_lap_time, degradation_rate_per_lap)

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
        ).dropna()

        if numeric_times.empty:
            raise ValueError(f"No numeric LapTime values for compound {compound!r} in race_df.")

        base_lap_time = float(numeric_times.median())
        degradation_rate = max(float((numeric_times.max() - numeric_times.min()) / max(1, len(numeric_times) - 1)), 0.0)
        return base_lap_time, degradation_rate

    def predict_lap_time(
        self,
        base_lap_time: float,
        degradation_rate: float,
        tyre_age: int
    ) -> float:
        """Predict lap time at a specific tyre age."""
        return float(base_lap_time + max(0.0, degradation_rate) * max(0, int(tyre_age)))
