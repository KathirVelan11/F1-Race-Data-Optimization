"""Integration package connecting Scope 1 and Scope 2."""
from src.f1_optimizer.integration.comparator import StrategyComparator, StrategyComparisonResult
from src.f1_optimizer.integration.pipeline import CombinedOptimizationPipeline

__all__ = [
    "StrategyComparator",
    "StrategyComparisonResult",
    "CombinedOptimizationPipeline",
]
