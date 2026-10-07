"""Tests for Scope 2 Goal Programming module."""
import pytest

from src.f1_optimizer.scope2.goals.goal_definitions import GoalTargets
from src.f1_optimizer.scope2.goals.weights import GoalWeights
from src.f1_optimizer.scope2.parameters.scope2_parameters import Scope2Parameters
from src.f1_optimizer.scope2.solver.goal_solver import Scope2GoalSolver


def test_scope2_time_penalty_tradeoff():
    """Verify Scope 2 race time is >= Scope 1 fastest time (T >= T*)."""
    parameters = Scope2Parameters(
        total_laps=58,
        compounds=["SOFT", "MEDIUM", "HARD"],
        pit_loss_p=13.0,
        targets=GoalTargets(target_race_time_t_star=4900.0, target_pit_stops_p_star=1, target_degradation_d_star=0.5),
        weights=GoalWeights(weight_time_w1=0.6, weight_pit_stops_w2=0.25, weight_degradation_w3=0.15),
        max_pit_stops=2,
        min_stint_length=5,
        max_stint_durability={"SOFT": 20, "MEDIUM": 30, "HARD": 50},
        predicted_lap_times={
            lap: {"SOFT": 86.0 + 0.05 * lap, "MEDIUM": 88.0 + 0.04 * lap, "HARD": 90.0 + 0.03 * lap}
            for lap in range(1, 59)
        },
        compound_degradations={"SOFT": 0.65, "MEDIUM": 0.35, "HARD": 0.2},
    )

    result = Scope2GoalSolver().solve(parameters)
    assert result.balanced_race_time_seconds >= parameters.targets.target_race_time_t_star
    assert result.pit_stop_count <= parameters.max_pit_stops
    assert result.stints


def test_scope2_weight_sensitivity():
    """Verify increasing w2 (pit stop penalty) drives model to fewer pit stops."""
    base = {
        "total_laps": 58,
        "compounds": ["SOFT", "MEDIUM", "HARD"],
        "pit_loss_p": 13.0,
        "targets": GoalTargets(target_race_time_t_star=4900.0, target_pit_stops_p_star=0, target_degradation_d_star=0.3),
        "max_pit_stops": 2,
        "min_stint_length": 5,
        "max_stint_durability": {"SOFT": 20, "MEDIUM": 30, "HARD": 50},
        "predicted_lap_times": {
            lap: {"SOFT": 86.0 + 0.05 * lap, "MEDIUM": 88.0 + 0.04 * lap, "HARD": 90.0 + 0.03 * lap}
            for lap in range(1, 59)
        },
        "compound_degradations": {"SOFT": 0.65, "MEDIUM": 0.35, "HARD": 0.2},
    }

    low_w = Scope2Parameters(**{**base, "weights": GoalWeights(weight_time_w1=0.2, weight_pit_stops_w2=0.1, weight_degradation_w3=0.7)})
    high_w = Scope2Parameters(**{**base, "weights": GoalWeights(weight_time_w1=0.1, weight_pit_stops_w2=0.8, weight_degradation_w3=0.1)})

    low_result = Scope2GoalSolver().solve(low_w)
    high_result = Scope2GoalSolver().solve(high_w)

    assert high_result.pit_stop_count <= low_result.pit_stop_count
