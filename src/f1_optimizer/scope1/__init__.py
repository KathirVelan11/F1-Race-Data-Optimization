"""Scope 1: Integrated Tyre & Pit-Stop Strategy (MILP).

Formulates and solves the single fastest race strategy by minimizing
total race time subject to compound choices, durability limits, and pit stop bounds.
"""
from src.f1_optimizer.scope1.service.scope1_service import Scope1Service
from src.f1_optimizer.scope1.output.scope1_result import Scope1OptimizationResult

__all__ = ["Scope1Service", "Scope1OptimizationResult"]
