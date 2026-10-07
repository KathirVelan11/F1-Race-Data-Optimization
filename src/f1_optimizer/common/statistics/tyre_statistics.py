"""Stint and degradation statistics per tyre compound."""
from typing import Dict, Any
import pandas as pd


class TyreStatisticsCalculator:
    """Computes empirical stint lengths, mean lap times, and wear profiles per compound."""

    @staticmethod
    def calculate_compound_summary(race_df: pd.DataFrame) -> Dict[str, Any]:
        """Aggregate stint length distributions and observed pace per tyre compound."""
        raise NotImplementedError("Will be implemented in Phase 2.")
