"""Tests for Scope 1 MILP module."""
import pytest

from src.f1_optimizer.common.race.race_context import RaceContext
from src.f1_optimizer.scope1.parameters.scope1_parameters import Scope1Parameters
from src.f1_optimizer.scope1.service.scope1_service import Scope1Service
from src.f1_optimizer.scope1.solver.milp_solver import Scope1MilpSolver


def test_scope1_model_feasibility():
    """Verify MILP model finds feasible solution for standard 58-lap race."""
    parameters = Scope1Parameters(
        total_laps=58,
        compounds=["SOFT", "MEDIUM", "HARD"],
        pit_loss_p=13.0,
        max_pit_stops=2,
        min_stint_length=5,
        max_stint_durability={"SOFT": 20, "MEDIUM": 30, "HARD": 50},
        predicted_lap_times={
            lap: {"SOFT": 86.0 + 0.05 * lap, "MEDIUM": 88.0 + 0.04 * lap, "HARD": 90.0 + 0.03 * lap}
            for lap in range(1, 59)
        },
    )

    result = Scope1MilpSolver().solve(parameters)
    assert result.minimum_predicted_race_time > 0
    assert result.pit_stop_count <= 2
    assert result.stints
    assert all(stint.stint_length >= 5 for stint in result.stints)


def test_scope1_max_pit_stops_constraint():
    """Verify MILP solution never exceeds 2 pit stops."""
    parameters = Scope1Parameters(
        total_laps=58,
        compounds=["SOFT", "MEDIUM", "HARD"],
        pit_loss_p=13.0,
        max_pit_stops=2,
        min_stint_length=5,
        max_stint_durability={"SOFT": 20, "MEDIUM": 30, "HARD": 50},
        predicted_lap_times={
            lap: {"SOFT": 86.5 + 0.04 * lap, "MEDIUM": 88.0 + 0.03 * lap, "HARD": 90.5 + 0.025 * lap}
            for lap in range(1, 59)
        },
    )

    result = Scope1MilpSolver().solve(parameters)
    assert result.pit_stop_count <= 2


def test_scope1_min_stint_length_constraint():
    """Verify all stints in optimal strategy have length >= 5 laps."""
    parameters = Scope1Parameters(
        total_laps=58,
        compounds=["SOFT", "MEDIUM", "HARD"],
        pit_loss_p=13.0,
        max_pit_stops=2,
        min_stint_length=5,
        max_stint_durability={"SOFT": 20, "MEDIUM": 30, "HARD": 50},
        predicted_lap_times={
            lap: {"SOFT": 86.0 + 0.05 * lap, "MEDIUM": 88.0 + 0.04 * lap, "HARD": 90.0 + 0.03 * lap}
            for lap in range(1, 59)
        },
    )

    result = Scope1MilpSolver().solve(parameters)
    assert all(stint.stint_length >= 5 for stint in result.stints)


def test_scope1_max_stint_durability_constraint():
    """Verify the solution never exceeds the compound's maximum durable stint length."""
    parameters = Scope1Parameters(
        total_laps=58,
        compounds=["SOFT", "MEDIUM", "HARD"],
        pit_loss_p=13.0,
        max_pit_stops=2,
        min_stint_length=5,
        max_stint_durability={"SOFT": 20, "MEDIUM": 30, "HARD": 50},
        predicted_lap_times={
            lap: {"SOFT": 85.0 + 0.02 * lap, "MEDIUM": 87.0 + 0.02 * lap, "HARD": 89.0 + 0.02 * lap}
            for lap in range(1, 59)
        },
    )

    result = Scope1MilpSolver().solve(parameters)
    assert all(stint.stint_length <= parameters.max_stint_durability[stint.compound.value] for stint in result.stints)


def test_scope1_service_run_optimization_from_race_context():
    """Verify the service layer constructs inputs from RaceContext and solves the MILP."""
    race_context = RaceContext(
        race_id=1,
        year=2024,
        race_name="Australian Grand Prix",
        total_laps=58,
        available_compounds=["SOFT", "MEDIUM", "HARD"],
        pit_loss_seconds=13.0,
        compound_base_times={"SOFT": 86.0, "MEDIUM": 88.0, "HARD": 90.0},
        compound_degradation_slopes={"SOFT": 0.05, "MEDIUM": 0.04, "HARD": 0.03},
        compound_durability_limits={"SOFT": 20, "MEDIUM": 30, "HARD": 50},
    )

    result = Scope1Service().run_optimization(race_context, max_pit_stops=2, min_stint_length=5)
    assert result.minimum_predicted_race_time > 0
    assert result.stints
    assert result.pit_stop_count <= 2
