"""Backend service orchestrator delegating API requests to the f1_optimizer package."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.f1_optimizer.common.data.dataset_loader import DatasetLoader
from src.f1_optimizer.common.utils.time_utils import lap_time_str_to_seconds
from src.f1_optimizer.scope1.parameters.scope1_parameters import Scope1Parameters
from src.f1_optimizer.scope1.solver.milp_solver import Scope1MilpSolver
from src.f1_optimizer.scope2.goals.goal_definitions import GoalTargets
from src.f1_optimizer.scope2.goals.weights import GoalWeights
from src.f1_optimizer.scope2.parameters.scope2_parameters import Scope2Parameters
from src.f1_optimizer.scope2.solver.goal_solver import Scope2GoalSolver


class BackendOptimizationRunner:
    """Delegates API execution requests to f1_optimizer core services."""

    def __init__(self, dataset_loader: Optional[DatasetLoader] = None):
        self.dataset_loader = dataset_loader or DatasetLoader()

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Return the current project data summary for the home dashboard."""
        df = self.dataset_loader.load_dataset()
        seasons = self.dataset_loader.get_available_seasons()
        total_races = int(df["Race"].nunique())
        total_drivers = int(df["Driver"].nunique())
        total_rows = int(len(df))
        years_range = f"{min(seasons)} - {max(seasons)}" if seasons else "N/A"
        return {
            "years": seasons,
            "years_range": years_range,
            "total_races": total_races,
            "total_drivers": total_drivers,
            "total_rows": total_rows,
            "source": "combined_dataset.csv",
        }

    def get_races_for_season(self, year: int) -> List[str]:
        """Return race names for a season."""
        return self.dataset_loader.get_races_for_season(year)

    def get_drivers_for_race(self, year: int, race_name: str) -> List[str]:
        """Return driver codes for a race."""
        return self.dataset_loader.get_drivers_for_race(year, race_name)

    def get_race_summary(self, year: int, race_name: str, driver_code: Optional[str] = None) -> Dict[str, Any]:
        """Return a compact race summary for the UI."""
        return self.dataset_loader.get_race_summary(year, race_name, driver_code)

    def _build_scope1_parameters(self, year: int, race_name: str, driver_code: Optional[str] = None) -> Scope1Parameters:
        """Construct a realistic Scope 1 parameter set from the selected race dataset."""
        df = self.dataset_loader.get_race_dataframe(year, race_name, driver_code)
        if df.empty:
            raise ValueError(f"No race data found for {race_name} ({year}).")

        if driver_code and (len(df) < 20 or int(df["Lap"].max()) < 10):
            df = self.dataset_loader.get_race_dataframe(year, race_name)

        compounds = ["SOFT", "MEDIUM", "HARD"]
        total_laps = int(df["Lap"].max()) if "Lap" in df.columns else 58
        lap_times_by_compound: Dict[int, Dict[str, float]] = {}

        for lap in range(1, total_laps + 1):
            lap_rows = df[df["Lap"] == lap]
            lap_times_by_compound[lap] = {}
            for compound in compounds:
                compound_rows = lap_rows[lap_rows["Compound"].astype(str).str.upper() == compound]
                if compound_rows.empty:
                    lap_times_by_compound[lap][compound] = 0.0
                    continue
                values = [
                    lap_time_str_to_seconds(str(value))
                    for value in compound_rows["LapTime"].tolist()
                    if lap_time_str_to_seconds(str(value)) is not None
                ]
                lap_times_by_compound[lap][compound] = float(sum(values) / len(values)) if values else 0.0

        for lap in range(1, total_laps + 1):
            for compound in compounds:
                value = lap_times_by_compound[lap].get(compound, 0.0)
                if value == 0.0:
                    base = {"SOFT": 86.0, "MEDIUM": 88.0, "HARD": 90.0}[compound]
                    degradation = {"SOFT": 0.05, "MEDIUM": 0.04, "HARD": 0.03}[compound]
                    lap_times_by_compound[lap][compound] = base + degradation * lap

        return Scope1Parameters(
            total_laps=total_laps,
            compounds=compounds,
            pit_loss_p=13.0,
            max_pit_stops=2,
            min_stint_length=5,
            max_stint_durability={"SOFT": 20, "MEDIUM": 30, "HARD": 50},
            predicted_lap_times=lap_times_by_compound,
        )

    def build_strategy_preview(self, year: int, race_name: str, driver_code: Optional[str] = None) -> Dict[str, Any]:
        """Return a real Scope 1 strategy preview for the frontend."""
        try:
            parameters = self._build_scope1_parameters(year, race_name, driver_code)
            result = Scope1MilpSolver().solve(parameters)
            stints = [
                {
                    "compound": stint.compound.value,
                    "start_lap": stint.start_lap,
                    "end_lap": stint.end_lap,
                    "lap_count": stint.stint_length,
                }
                for stint in result.stints
            ]
            return {
                "year": year,
                "race_name": race_name,
                "driver_code": driver_code,
                "total_laps": parameters.total_laps,
                "fastest_compound": stints[0]["compound"] if stints else "SOFT",
                "estimated_race_time_seconds": round(result.minimum_predicted_race_time, 2),
                "strategy": stints,
                "solver_status": result.solver_status,
                "pit_laps": result.optimal_pit_laps,
                "message": "Scope 1 MILP solved successfully.",
            }
        except Exception as exc:  # pragma: no cover - user-facing fallback
            return {
                "year": year,
                "race_name": race_name,
                "driver_code": driver_code,
                "strategy": [],
                "message": f"Optimization could not be executed: {exc}",
            }

    def run_scope1(self, request_data: Any) -> Any:
        """Solve the Scope 1 MILP model for the chosen race selection."""
        year = int(request_data.get("year", 2024))
        race_name = str(request_data.get("race_name", "Australian Grand Prix"))
        driver_code = request_data.get("driver_code")
        return self.build_strategy_preview(year, race_name, driver_code)

    def run_scope2(self, request_data: Any) -> Any:
        """Solve the Scope 2 goal-programming model for the selected race."""
        year = int(request_data.get("year", 2024))
        race_name = str(request_data.get("race_name", "Australian Grand Prix"))
        driver_code = request_data.get("driver_code")

        try:
            scope1 = self.build_strategy_preview(year, race_name, driver_code)
            scope1_target = float(scope1.get("estimated_race_time_seconds", 0.0))
            weights = GoalWeights(**(request_data.get("weights") or {})) if request_data.get("weights") else GoalWeights()
            df = self.dataset_loader.get_race_dataframe(year, race_name, driver_code)
            if df.empty:
                raise ValueError(f"No race data found for {race_name} ({year}).")

            compounds = ["SOFT", "MEDIUM", "HARD"]
            total_laps = int(df["Lap"].max()) if "Lap" in df.columns else 58
            predicted = {
                lap: {compound: 90.0 + 0.03 * lap for compound in compounds}
                for lap in range(1, total_laps + 1)
            }
            for lap in range(1, total_laps + 1):
                for compound in compounds:
                    predicted[lap][compound] = {
                        "SOFT": 86.0 + 0.05 * lap,
                        "MEDIUM": 88.0 + 0.04 * lap,
                        "HARD": 90.0 + 0.03 * lap,
                    }[compound]

            params = Scope2Parameters(
                total_laps=total_laps,
                compounds=compounds,
                pit_loss_p=13.0,
                targets=GoalTargets(
                    target_race_time_t_star=scope1_target,
                    target_pit_stops_p_star=1,
                    target_degradation_d_star=0.4,
                ),
                weights=weights,
                max_pit_stops=2,
                min_stint_length=5,
                max_stint_durability={"SOFT": 20, "MEDIUM": 30, "HARD": 50},
                predicted_lap_times=predicted,
                compound_degradations={"SOFT": 0.65, "MEDIUM": 0.35, "HARD": 0.2},
            )
            result = Scope2GoalSolver().solve(params)
            stints = [
                {"compound": stint.compound.value, "start_lap": stint.start_lap, "end_lap": stint.end_lap, "lap_count": stint.stint_length}
                for stint in result.stints
            ]
            return {
                "year": year,
                "race_name": race_name,
                "driver_code": driver_code,
                "total_laps": total_laps,
                "balanced_race_time_seconds": round(result.balanced_race_time_seconds, 2),
                "time_delta_vs_fastest_seconds": round(result.time_delta_vs_fastest_seconds, 2),
                "pit_stop_count": result.pit_stop_count,
                "strategy": stints,
                "deviations": result.deviations.model_dump(),
                "objective_value_z": round(result.objective_value_z, 4),
                "solver_status": result.solver_status,
                "message": "Scope 2 goal programming solved successfully.",
            }
        except Exception as exc:  # pragma: no cover - user-facing fallback
            return {
                "year": year,
                "race_name": race_name,
                "driver_code": driver_code,
                "strategy": [],
                "message": f"Goal programming could not be executed: {exc}",
            }

    def run_comparison(self, request_data: Any) -> Any:
        """Compare the fastest and balanced strategies."""
        scope1 = self.run_scope1(request_data)
        scope2 = self.run_scope2(request_data)
        delta = 0.0
        try:
            target = float(scope1.get("estimated_race_time_seconds", 0.0))
            balanced = float(scope2.get("balanced_race_time_seconds", target))
            delta = balanced - target
        except Exception:
            delta = 0.0
        return {
            "scope1": scope1,
            "scope2": scope2,
            "time_delta_seconds": round(delta, 2),
            "comparison_note": "Balanced model trades a small time penalty to reduce strategic emphasis on raw speed.",
        }
