"""Stint and degradation statistics per tyre compound."""
from typing import Dict, Any
import pandas as pd


class TyreStatisticsCalculator:
    """Computes empirical stint lengths, mean lap times, and wear profiles per compound."""

    @staticmethod
    def calculate_compound_summary(race_df: pd.DataFrame) -> Dict[str, Any]:
        """Aggregate stint length distributions and observed pace per tyre compound."""
        df = race_df.dropna(subset=["Stint", "TyreLife", "Compound"]).copy()
        df["Compound"] = df["Compound"].astype(str).str.upper()
        if df.empty:
            return {}

        group_keys = [key for key in ("Year", "Race", "Driver") if key in df.columns]
        stint_max_life = (
            df.groupby(group_keys + ["Stint", "Compound"])["TyreLife"].max()
            if group_keys
            else df.groupby(["Stint", "Compound"])["TyreLife"].max()
        )

        summary: Dict[str, Any] = {}
        for compound, values in stint_max_life.groupby("Compound"):
            summary[compound] = {
                "mean_stint_life": float(values.mean()),
                "max_stint_life": float(values.max()),
                "stint_count": int(values.count()),
            }
        return summary

    @staticmethod
    def calculate_mean_max_stint_life(race_df: pd.DataFrame) -> Dict[str, int]:
        """Return the mean max TyreLife reached per stint, per compound, rounded to whole laps."""
        summary = TyreStatisticsCalculator.calculate_compound_summary(race_df)
        return {
            compound: max(1, round(stats["mean_stint_life"]))
            for compound, stats in summary.items()
        }
