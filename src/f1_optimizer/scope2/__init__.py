"""Scope 2: Multi-Objective Strategy Selection (Goal Programming).

Balances competing priorities (race time, pit stop frequency, tyre degradation)
by minimizing weighted deviations from achievable targets.
"""
from src.f1_optimizer.scope2.service.scope2_service import Scope2Service
from src.f1_optimizer.scope2.output.scope2_result import Scope2OptimizationResult

__all__ = ["Scope2Service", "Scope2OptimizationResult"]
