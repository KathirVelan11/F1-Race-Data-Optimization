"""Validation module comparing optimizer predictions against actual Kaggle race results."""
from typing import Dict, Any
import pandas as pd
from pydantic import BaseModel

from src.f1_optimizer.common.schemas.strategy import StrategyResult


class ValidationReport(BaseModel):
    """Validation report comparing predicted strategy with actual historical results."""
    race_id: int
    driver_code: str
    predicted_time_seconds: float
    actual_time_seconds: float
    delta_seconds: float
    percentage_error: float
    predicted_pit_count: int
    actual_pit_count: int


class StrategyResultValidator:
    """Validates predicted strategy and time against historical results.csv."""

    def validate_against_actual(
        self,
        strategy_result: StrategyResult,
        race_id: int,
        driver_code: str,
        results_df: pd.DataFrame
    ) -> ValidationReport:
        """Compare predicted strategy metrics against ground truth results."""
        raise NotImplementedError("Will be implemented in Phase 5.")
