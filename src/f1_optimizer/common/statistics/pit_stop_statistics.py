"""Empirical pit stop duration and time loss statistics."""
from typing import Dict, Any
import pandas as pd


class PitStopStatisticsCalculator:
    """Calculates pit lane delta and stop execution times from historical data."""

    @staticmethod
    def calculate_pit_loss_summary(race_df: pd.DataFrame) -> Dict[str, Any]:
        """Compute mean pit stop duration and estimated track position loss."""
        raise NotImplementedError("Will be implemented in Phase 2.")
