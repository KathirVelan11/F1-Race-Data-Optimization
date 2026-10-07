"""Comparison and trade-off analysis between Scope 1 and Scope 2 strategies."""
from typing import Dict, Any
from pydantic import BaseModel, Field

from src.f1_optimizer.scope1.output.scope1_result import Scope1OptimizationResult
from src.f1_optimizer.scope2.output.scope2_result import Scope2OptimizationResult


class StrategyComparisonResult(BaseModel):
    """Side-by-side comparison of Scope 1 (Fastest) vs Scope 2 (Balanced).
    
    Sample table from PPT Slide 15:
        Model 1 (MILP) vs Model 2 (Goal Programming)
        Strategy stints
        Race time comparison (e.g. 1:28:33.2 vs 1:28:35.1, delta +1.9s)
        Pit stops comparison
        Trade-off summary
    """
    scope1_result: Scope1OptimizationResult
    scope2_result: Scope2OptimizationResult
    time_delta_seconds: float = Field(..., description="Time added by balanced strategy (T_scope2 - T_scope1)")
    pit_stops_saved: int = Field(..., description="Pit stops saved by balanced strategy (P_scope1 - P_scope2)")
    recommendation_summary: str = Field(..., description="Natural language strategic recommendation")


class StrategyComparator:
    """Computes trade-offs, deltas, and risk/reward balances between both models."""

    @staticmethod
    def compare(
        scope1_result: Scope1OptimizationResult,
        scope2_result: Scope2OptimizationResult
    ) -> StrategyComparisonResult:
        """Generate structured comparison and trade-off metrics between Scope 1 and Scope 2."""
        raise NotImplementedError("Will be implemented in Phase 5.")
