"""Race filtering and lap cleaning preprocessor."""
from typing import Optional
import pandas as pd


class RacePreprocessor:
    """Filters race sessions, removes safety car anomalies, and standardizes lap times."""

    def filter_race_session(
        self,
        df: pd.DataFrame,
        year: int,
        race_name: str,
        driver_code: Optional[str] = None
    ) -> pd.DataFrame:
        """Filter the dataset down to a specific race session and optional driver."""
        raise NotImplementedError("Will be implemented in Phase 2.")

    def clean_outlier_laps(
        self,
        race_df: pd.DataFrame,
        max_deviation_sigma: float = 3.0
    ) -> pd.DataFrame:
        """Filter out abnormal laps (e.g. Safety Car, Virtual Safety Car, yellow flags, in-laps)."""
        raise NotImplementedError("Will be implemented in Phase 2.")
