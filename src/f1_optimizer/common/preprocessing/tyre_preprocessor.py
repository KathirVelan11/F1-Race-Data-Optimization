"""Superseded: this module's original design (collapse every compound down to a fixed
SOFT/MEDIUM/HARD set, discard INTERMEDIATE/WET laps) was abandoned in favor of using
every compound actually present in a race's real data, legacy names and wet-weather
compounds included -- see BackendOptimizationRunner._get_available_compounds, which is
what the live app uses instead. Left unimplemented intentionally rather than building
out a normalization step the project no longer wants."""
import pandas as pd


class TyrePreprocessor:
    """Deprecated. See BackendOptimizationRunner._get_available_compounds instead."""

    @staticmethod
    def normalize_dry_compounds(df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError(
            "Superseded by BackendOptimizationRunner._get_available_compounds, "
            "which uses every real compound present instead of normalizing to SOFT/MEDIUM/HARD."
        )

    @staticmethod
    def filter_dry_laps(df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError(
            "Superseded: the project now includes INTERMEDIATE/WET laps rather than "
            "filtering them out. See BackendOptimizationRunner._get_available_compounds."
        )
