"""Integrated execution pipeline connecting Scope 1, Scope 2, and Comparison."""
from typing import Optional
from pydantic import BaseModel

from src.f1_optimizer.common.race.race_context import RaceContext
from src.f1_optimizer.scope1.service.scope1_service import Scope1Service
from src.f1_optimizer.scope2.goals.weights import GoalWeights
from src.f1_optimizer.scope2.service.scope2_service import Scope2Service
from src.f1_optimizer.integration.comparator import StrategyComparator, StrategyComparisonResult


class CombinedOptimizationPipeline:
    """Orchestrates end-to-end flow:
    1. Runs Scope 1 (MILP) to find fastest race time T*.
    2. Passes T* as target into Scope 2 (Goal Programming).
    3. Runs Scope 2 with user priority weights.
    4. Generates side-by-side comparison and trade-off metrics.
    """

    def __init__(
        self,
        scope1_service: Optional[Scope1Service] = None,
        scope2_service: Optional[Scope2Service] = None,
        comparator: Optional[StrategyComparator] = None
    ):
        self.scope1_service = scope1_service or Scope1Service()
        self.scope2_service = scope2_service or Scope2Service()
        self.comparator = comparator or StrategyComparator()

    def run_full_pipeline(
        self,
        race_context: RaceContext,
        target_pit_stops: int,
        target_degradation: float,
        weights: GoalWeights
    ) -> StrategyComparisonResult:
        """Execute end-to-end optimization and return comparative results."""
        raise NotImplementedError("Will be implemented in Phase 5.")
