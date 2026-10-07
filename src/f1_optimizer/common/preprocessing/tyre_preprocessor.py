"""Tyre compound mapping and normalization preprocessor."""
import pandas as pd


class TyrePreprocessor:
    """Standardizes tyre compound names across historical regulation changes.
    
    Handles 2018 compound names (HYPERSOFT, ULTRASOFT, SUPERSOFT) mapping to standard (SOFT),
    and filters non-dry compounds (INTERMEDIATE, WET) for standard dry-race optimization.
    """

    @staticmethod
    def normalize_dry_compounds(df: pd.DataFrame) -> pd.DataFrame:
        """Map historical compounds to standard SOFT, MEDIUM, HARD."""
        raise NotImplementedError("Will be implemented in Phase 2.")

    @staticmethod
    def filter_dry_laps(df: pd.DataFrame) -> pd.DataFrame:
        """Filter out wet/intermediate running for dry race strategy models."""
        raise NotImplementedError("Will be implemented in Phase 2.")
