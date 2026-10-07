"""Tyre degradation estimation and curve-fitting models."""
from typing import Dict, Any, Tuple
import pandas as pd


class TyreDegradationModel:
    """Estimates empirical tyre degradation slopes and baseline lap times per compound."""

    def fit_example_degradation(self) -> Dict[str, float]:
        """Return a simple non-negative degradation profile for the project's default compounds."""
        return {
            "SOFT": 0.75,
            "MEDIUM": 0.45,
            "HARD": 0.25,
        }

    def fit_compound_degradation(
        self,
        race_df: pd.DataFrame,
        compound: str
    ) -> Tuple[float, float]:
        """Fit degradation slope and base lap time for a specific tyre compound.
        
        Returns:
            (base_lap_time, degradation_rate_per_lap)
        """
        if race_df is None or race_df.empty:
            return 90.0, 0.0

        compound_column = None
        for name in ["Compound", "compound", "TyreCompound"]:
            if name in race_df.columns:
                compound_column = name
                break

        if compound_column is None:
            return 90.0, 0.0

        subset = race_df[race_df[compound_column].astype(str).str.upper() == str(compound).upper()]
        if subset.empty:
            return 90.0, 0.0

        lap_times = subset["LapTime"] if "LapTime" in subset.columns else subset.iloc[:, 0]
        numeric_times = pd.to_numeric(lap_times.replace({"": None, "nan": None}), errors="coerce").dropna()

        if numeric_times.empty:
            return 90.0, 0.0

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
