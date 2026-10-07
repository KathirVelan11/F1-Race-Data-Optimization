"""Standardized dataset loader interface for the combined F1 dataset.

Consumes the master CSV at data/processed/combined_dataset.csv without modifying or
duplicating it, providing a single data-access abstraction for both Scope 1 and Scope 2.
"""
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.f1_optimizer.common.utils.time_utils import lap_time_str_to_seconds

try:
    from src.f1_optimizer.config.settings import settings
except ImportError:
    try:
        from f1_optimizer.config.settings import settings  # type: ignore
    except ImportError:
        from src.f1_optimizer.config.settings import settings  # type: ignore


class DatasetLoader:
    """Loads and caches the combined F1 dataset for optimization workflows."""

    def __init__(self, dataset_path: Optional[Path] = None):
        self.dataset_path = dataset_path or settings.processed_data_path
        self._cached_df: Optional[pd.DataFrame] = None

    def load_dataset(self) -> pd.DataFrame:
        """Load the full dataset into memory with caching."""
        if self._cached_df is not None:
            return self._cached_df.copy()

        dataset_path = Path(self.dataset_path)
        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found at: {dataset_path}")

        df = pd.read_csv(dataset_path)
        if "LapTime" in df.columns:
            df["LapTime"] = df["LapTime"].fillna("0:00.000").astype(str)
        if "pit_duration" in df.columns:
            df["pit_duration"] = pd.to_numeric(df["pit_duration"], errors="coerce")
        if "Lap" in df.columns:
            df["Lap"] = pd.to_numeric(df["Lap"], errors="coerce").fillna(0).astype(int)

        self._cached_df = df.copy()
        return self._cached_df.copy()

    def get_available_seasons(self) -> List[int]:
        """Return unique seasons available in the dataset."""
        df = self.load_dataset()
        return sorted(df["Year"].dropna().astype(int).unique().tolist())

    def get_races_for_season(self, year: int) -> List[str]:
        """Return unique race names for a given year."""
        df = self.load_dataset()
        races = df.loc[df["Year"] == int(year), "Race"].dropna().unique().tolist()
        return sorted(races)

    def get_drivers_for_race(self, year: int, race_name: str) -> List[str]:
        """Return unique driver codes for a given race."""
        df = self.load_dataset()
        drivers = df.loc[
            (df["Year"] == int(year)) & (df["Race"] == race_name),
            "Driver",
        ].dropna().unique().tolist()
        return sorted(drivers)

    def get_race_dataframe(self, year: int, race_name: str, driver_code: Optional[str] = None) -> pd.DataFrame:
        """Return the lap dataframe for one race, optionally filtered to a driver."""
        df = self.load_dataset()
        mask = (df["Year"] == int(year)) & (df["Race"] == race_name)
        if driver_code:
            mask &= (df["Driver"] == str(driver_code).upper())
        return df.loc[mask].copy().sort_values(["Driver", "Lap"]).reset_index(drop=True)

    def get_race_summary(self, year: int, race_name: str, driver_code: Optional[str] = None) -> dict:
        """Return a compact summary of a race for the API and UI."""
        df = self.get_race_dataframe(year, race_name, driver_code)
        if df.empty:
            return {"year": year, "race_name": race_name, "driver_code": driver_code, "total_laps": 0, "drivers": []}

        total_laps = int(df["Lap"].max())
        drivers = sorted(df["Driver"].dropna().unique().tolist())
        lap_times = df["LapTime"].map(lambda value: lap_time_str_to_seconds(str(value))).dropna()
        avg_lap_time = float(lap_times.mean()) if not lap_times.empty else 0.0

        return {
            "year": int(year),
            "race_name": race_name,
            "driver_code": driver_code,
            "total_laps": total_laps,
            "drivers": drivers,
            "average_lap_time_seconds": round(avg_lap_time, 3),
            "row_count": int(len(df)),
        }
