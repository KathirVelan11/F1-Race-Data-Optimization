"""Backend service orchestrator delegating API requests to the f1_optimizer package."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from src.f1_optimizer.common.data.dataset_loader import DatasetLoader
from src.f1_optimizer.common.statistics.tyre_statistics import TyreStatisticsCalculator
from src.f1_optimizer.common.utils.time_utils import lap_time_str_to_seconds
from src.f1_optimizer.scope1.parameters.scope1_parameters import Scope1Parameters
from src.f1_optimizer.scope1.solver.milp_solver import Scope1MilpSolver
from src.f1_optimizer.scope2.goals.goal_definitions import GoalTargets
from src.f1_optimizer.scope2.goals.weights import GoalWeights
from src.f1_optimizer.scope2.parameters.scope2_parameters import Scope2Parameters
from src.f1_optimizer.scope2.solver.goal_solver import Scope2GoalSolver

# Pirelli compound softness ranking (softest -> hardest). Softer compounds grip harder
# but wear faster; this physical ordering is used for degradation and base-pace fallbacks
# since per-lap regression on this dataset is too confounded by fuel load / traffic / SC
# periods to reliably rank compounds on its own.
COMPOUND_SOFTNESS_ORDER: List[str] = [
    "HYPERSOFT",
    "ULTRASOFT",
    "SUPERSOFT",
    "SOFT",
    "MEDIUM",
    "HARD",
    "INTERMEDIATE",
    "WET",
]
EXCLUDED_COMPOUNDS = {"NAN", "UNKNOWN", "NONE", ""}


class BackendOptimizationRunner:
    """Delegates API execution requests to f1_optimizer core services."""

    def __init__(self, dataset_loader: Optional[DatasetLoader] = None):
        self.dataset_loader = dataset_loader or DatasetLoader()
        self._compound_durability_cache: Optional[Dict[str, int]] = None
        self._compound_base_pace_cache: Optional[Dict[str, float]] = None
        self._pit_loss_by_race_cache: Optional[Dict[Any, float]] = None
        self._pit_loss_by_circuit_cache: Optional[Dict[str, float]] = None
        self._pit_loss_global_mean: Optional[float] = None

    def _get_pit_loss_seconds(self, year: int, race_name: str) -> float:
        """Mean real pit-stop time loss (seconds) for this race, since the cost varies a
        lot by circuit (pit lane length, speed limit, drive-through distance) -- e.g. the
        dataset shows ~20.6s average at Australia vs ~32.7s at Imola.

        Falls back from race-specific -> circuit-wide (ignoring year) -> dataset-wide mean,
        since some races have too few recorded stops to trust alone.
        """
        if self._pit_loss_by_race_cache is None:
            full_df = self.dataset_loader.load_dataset()
            df = full_df.copy()
            df["pit_duration"] = pd.to_numeric(df["pit_duration"], errors="coerce")
            valid = df.dropna(subset=["pit_duration"])
            valid = valid[(valid["pit_duration"] >= 10) & (valid["pit_duration"] <= 60)]

            by_race = valid.groupby(["Year", "Race"])["pit_duration"].mean()
            self._pit_loss_by_race_cache = {
                (int(year_key), race_key): float(value) for (year_key, race_key), value in by_race.items()
            }
            by_circuit = valid.groupby("Race")["pit_duration"].mean()
            self._pit_loss_by_circuit_cache = {race_key: float(value) for race_key, value in by_circuit.items()}
            self._pit_loss_global_mean = float(valid["pit_duration"].mean()) if not valid.empty else 13.0

        race_key = (int(year), race_name)
        if race_key in self._pit_loss_by_race_cache:
            return round(self._pit_loss_by_race_cache[race_key], 2)
        if race_name in (self._pit_loss_by_circuit_cache or {}):
            return round(self._pit_loss_by_circuit_cache[race_name], 2)
        return round(self._pit_loss_global_mean or 13.0, 2)

    def _resolve_strategy_constraints(
        self,
        race_df: "pd.DataFrame",
        total_laps: int,
        requested_max_pit_stops: Optional[int] = None,
        requested_min_stint_length: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Resolve max_pit_stops / min_stint_length from optional user input, defaulting to
        and validating against this race's real data so a bad input (e.g. 0 or 100) can
        never make the solver infeasible.

        Returns the resolved values plus the data-driven bounds, so the UI can show the
        user what range is actually valid and why their input was adjusted, if it was.
        """
        stint_lengths = (
            race_df.dropna(subset=["Stint", "TyreLife"])
            .groupby(["Driver", "Stint"])["TyreLife"]
            .max()
        )
        real_pit_counts = (
            race_df.dropna(subset=["Stint"]).groupby("Driver")["Stint"].max() - 1
        )

        # Max pit stops: default to the race's observed 90th percentile (rounded up),
        # floor 1, so the solver always has room for at least one real strategy choice.
        default_max_pit_stops = max(1, int(real_pit_counts.quantile(0.9)) if not real_pit_counts.empty else 2)
        upper_bound_pit_stops = max(default_max_pit_stops, int(real_pit_counts.max()) if not real_pit_counts.empty else 4, 1)
        if requested_max_pit_stops is None:
            max_pit_stops = default_max_pit_stops
        else:
            max_pit_stops = max(1, min(int(requested_max_pit_stops), upper_bound_pit_stops))

        # Min stint length: default to a conservative floor below which almost no real
        # stint falls (5th percentile), never above what total_laps/stint-count allows.
        observed_min = int(stint_lengths.quantile(0.05)) if not stint_lengths.empty else 3
        default_min_stint_length = max(1, min(observed_min, 5))
        upper_bound_stint_length = max(1, total_laps // max(1, max_pit_stops + 1))
        if requested_min_stint_length is None:
            min_stint_length = min(default_min_stint_length, upper_bound_stint_length)
        else:
            min_stint_length = max(1, min(int(requested_min_stint_length), upper_bound_stint_length))

        return {
            "max_pit_stops": max_pit_stops,
            "min_stint_length": min_stint_length,
            "max_pit_stops_valid_range": [1, upper_bound_pit_stops],
            "min_stint_length_valid_range": [1, upper_bound_stint_length],
        }

    def _get_max_stint_durability(
        self,
        compounds: List[str],
        race_df: Optional["pd.DataFrame"] = None,
        total_laps: Optional[int] = None,
        max_stints: int = 3,
    ) -> Dict[str, int]:
        """Mean max TyreLife reached per stint, by compound.

        Prefers durability computed from the specific race (tyre wear varies a lot by
        circuit, e.g. Monaco's short low-speed laps let tyres last far longer than the
        global average), falling back to the dataset-wide mean for compounds without
        enough race-specific stint data.

        `max_stints` is max_pit_stops + 1 for whatever max_pit_stops the solver will
        actually use (which may be user-supplied) -- the floor below must match that
        exact stint count, otherwise a durability guarantee sized for 3 stints can make
        the solver infeasible when the user requests fewer stops (less room per stint).
        """
        if self._compound_durability_cache is None:
            full_df = self.dataset_loader.load_dataset()
            self._compound_durability_cache = TyreStatisticsCalculator.calculate_mean_max_stint_life(full_df)

        race_durability: Dict[str, int] = {}
        if race_df is not None and not race_df.empty:
            race_durability = TyreStatisticsCalculator.calculate_mean_max_stint_life(race_df)

        fallback = max(self._compound_durability_cache.values(), default=30)
        durability = {
            compound: race_durability.get(
                compound, self._compound_durability_cache.get(compound, fallback)
            )
            for compound in compounds
        }

        if total_laps:
            min_required = -(-total_laps // max(1, max_stints))  # ceil(total_laps / max_stints)
            durability = {compound: max(value, min_required) for compound, value in durability.items()}

        return durability

    def _build_predicted_lap_times(
        self, df: "pd.DataFrame", compounds: List[str], total_laps: int
    ) -> Dict[int, Dict[str, float]]:
        """Average real recorded lap times per (lap, compound); fall back to a data-driven
        base pace plus a softness-ranked degradation slope where no laps were recorded."""
        base_pace = self._get_compound_base_pace(compounds)
        degradation_index = self._get_compound_degradation_index(compounds)
        lap_times: Dict[int, Dict[str, float]] = {}

        for lap in range(1, total_laps + 1):
            lap_rows = df[df["Lap"] == lap]
            lap_times[lap] = {}
            for compound in compounds:
                compound_rows = lap_rows[lap_rows["Compound"].astype(str).str.upper() == compound]
                values = [
                    lap_time_str_to_seconds(str(value))
                    for value in compound_rows["LapTime"].tolist()
                    if lap_time_str_to_seconds(str(value)) is not None
                ]
                lap_times[lap][compound] = float(sum(values) / len(values)) if values else 0.0

        for lap in range(1, total_laps + 1):
            for compound in compounds:
                if lap_times[lap].get(compound, 0.0) == 0.0:
                    base = base_pace.get(compound, 90.0)
                    degradation = 0.02 + 0.06 * degradation_index.get(compound, 0.5)
                    lap_times[lap][compound] = base + degradation * lap

        return lap_times

    def _get_available_compounds(self, race_df: "pd.DataFrame") -> List[str]:
        """Return the compounds actually present in a race's data, ordered softest to hardest.

        Different eras used different compound names (2018 used
        HYPERSOFT/ULTRASOFT/SUPERSOFT, 2019+ consolidated to SOFT/MEDIUM/HARD), and wet
        races add INTERMEDIATE/WET, so the usable compound set is derived per-race
        instead of being hardcoded.
        """
        present = set(race_df["Compound"].astype(str).str.upper().unique().tolist())
        present -= EXCLUDED_COMPOUNDS
        ordered = [c for c in COMPOUND_SOFTNESS_ORDER if c in present]
        return ordered or ["SOFT", "MEDIUM", "HARD"]

    def _get_compound_base_pace(self, compounds: List[str]) -> Dict[str, float]:
        """Mean lap time (seconds) per compound across the full dataset, for fallback laps
        where a race has no recorded laps on a given compound."""
        if self._compound_base_pace_cache is None:
            full_df = self.dataset_loader.load_dataset()
            df = full_df.copy()
            df["Compound"] = df["Compound"].astype(str).str.upper()
            df["LapSeconds"] = df["LapTime"].map(lambda value: lap_time_str_to_seconds(str(value)))
            df = df.dropna(subset=["LapSeconds"])
            df = df[~df["Compound"].isin(EXCLUDED_COMPOUNDS)]
            self._compound_base_pace_cache = df.groupby("Compound")["LapSeconds"].mean().to_dict()

        fallback = float(sum(self._compound_base_pace_cache.values()) / len(self._compound_base_pace_cache)) \
            if self._compound_base_pace_cache else 90.0
        return {compound: float(self._compound_base_pace_cache.get(compound, fallback)) for compound in compounds}

    @staticmethod
    def _get_compound_degradation_index(compounds: List[str]) -> Dict[str, float]:
        """Relative degradation severity per compound, 0 (lasts longest) to 1 (wears fastest).

        Ranked by the standard Pirelli softness order rather than a regression on raw lap
        times: this dataset's lap times are dominated by fuel burn-off, traffic, and
        safety-car periods, which makes a direct per-lap degradation regression unreliable,
        whereas the softer-degrades-faster physical ordering is well established.
        """
        ranked = [c for c in COMPOUND_SOFTNESS_ORDER if c in compounds]
        if len(ranked) <= 1:
            return {compound: 0.5 for compound in compounds}
        n = len(ranked)
        return {compound: round(1.0 - (idx / (n - 1)), 3) for idx, compound in enumerate(ranked)}

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Return the current project data summary for the home dashboard."""
        df = self.dataset_loader.load_dataset()
        seasons = self.dataset_loader.get_available_seasons()
        total_races = int(df.drop_duplicates(["Year", "Race"]).shape[0])
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

    def get_dataset_overview(self) -> Dict[str, Any]:
        """Return a detailed breakdown of the combined dataset for the UI overview panel."""
        df = self.dataset_loader.load_dataset()
        df = df.copy()
        df["Compound"] = df["Compound"].astype(str).str.upper()

        races_per_year = (
            df.drop_duplicates(["Year", "Race"]).groupby("Year").size().sort_index()
        )
        compound_counts = (
            df[df["Compound"] != "NAN"]["Compound"].value_counts().sort_values(ascending=False)
        )
        pit_stops = df["pit_duration"].dropna()
        durability = TyreStatisticsCalculator.calculate_mean_max_stint_life(df)

        return {
            "total_rows": int(len(df)),
            "total_races": int(df.drop_duplicates(["Year", "Race"]).shape[0]),
            "total_drivers": int(df["Driver"].nunique()),
            "total_teams": int(df["Team"].nunique()),
            "years_range": f"{int(df['Year'].min())} - {int(df['Year'].max())}",
            "races_per_year": {int(year): int(count) for year, count in races_per_year.items()},
            "compound_distribution": {
                compound: int(count) for compound, count in compound_counts.items()
            },
            "pit_stop_stats": {
                "count": int(pit_stops.shape[0]),
                "mean_duration_seconds": round(float(pit_stops.mean()), 3) if not pit_stops.empty else 0.0,
                "min_duration_seconds": round(float(pit_stops.min()), 3) if not pit_stops.empty else 0.0,
                "max_duration_seconds": round(float(pit_stops.max()), 3) if not pit_stops.empty else 0.0,
            },
            "mean_max_stint_life_by_compound": durability,
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

    def _build_scope1_parameters(
        self,
        year: int,
        race_name: str,
        driver_code: Optional[str] = None,
        max_pit_stops: Optional[int] = None,
        min_stint_length: Optional[int] = None,
    ) -> tuple[Scope1Parameters, Dict[str, Any]]:
        """Construct a realistic Scope 1 parameter set from the selected race dataset."""
        df = self.dataset_loader.get_race_dataframe(year, race_name, driver_code)
        if df.empty:
            raise ValueError(f"No race data found for {race_name} ({year}).")

        if driver_code and (len(df) < 20 or int(df["Lap"].max()) < 10):
            df = self.dataset_loader.get_race_dataframe(year, race_name)

        full_race_df = self.dataset_loader.get_race_dataframe(year, race_name)
        compounds = self._get_available_compounds(df)
        total_laps = int(df["Lap"].max()) if "Lap" in df.columns else 58
        lap_times_by_compound = self._build_predicted_lap_times(df, compounds, total_laps)
        constraints = self._resolve_strategy_constraints(
            full_race_df, total_laps, max_pit_stops, min_stint_length
        )

        parameters = Scope1Parameters(
            total_laps=total_laps,
            compounds=compounds,
            pit_loss_p=self._get_pit_loss_seconds(year, race_name),
            max_pit_stops=constraints["max_pit_stops"],
            min_stint_length=constraints["min_stint_length"],
            max_stint_durability=self._get_max_stint_durability(
                compounds,
                race_df=full_race_df,
                total_laps=total_laps,
                max_stints=constraints["max_pit_stops"] + 1,
            ),
            predicted_lap_times=lap_times_by_compound,
        )
        return parameters, constraints

    def build_strategy_preview(
        self,
        year: int,
        race_name: str,
        driver_code: Optional[str] = None,
        max_pit_stops: Optional[int] = None,
        min_stint_length: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Return a real Scope 1 strategy preview for the frontend."""
        try:
            parameters, constraints = self._build_scope1_parameters(
                year, race_name, driver_code, max_pit_stops, min_stint_length
            )
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
                "pit_loss_seconds": parameters.pit_loss_p,
                "max_pit_stops": parameters.max_pit_stops,
                "min_stint_length": parameters.min_stint_length,
                "max_pit_stops_valid_range": constraints["max_pit_stops_valid_range"],
                "min_stint_length_valid_range": constraints["min_stint_length_valid_range"],
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
        max_pit_stops = request_data.get("max_pit_stops")
        min_stint_length = request_data.get("min_stint_length")
        return self.build_strategy_preview(year, race_name, driver_code, max_pit_stops, min_stint_length)

    def run_scope2(self, request_data: Any) -> Any:
        """Solve the Scope 2 goal-programming model for the selected race."""
        year = int(request_data.get("year", 2024))
        race_name = str(request_data.get("race_name", "Australian Grand Prix"))
        driver_code = request_data.get("driver_code")
        max_pit_stops_input = request_data.get("max_pit_stops")
        min_stint_length_input = request_data.get("min_stint_length")

        try:
            scope1 = self.build_strategy_preview(
                year, race_name, driver_code, max_pit_stops_input, min_stint_length_input
            )
            scope1_target = float(scope1.get("estimated_race_time_seconds", 0.0))
            weights = GoalWeights(**(request_data.get("weights") or {})) if request_data.get("weights") else GoalWeights()
            df = self.dataset_loader.get_race_dataframe(year, race_name, driver_code)
            if df.empty:
                raise ValueError(f"No race data found for {race_name} ({year}).")

            full_race_df = self.dataset_loader.get_race_dataframe(year, race_name)
            compounds = self._get_available_compounds(df)
            total_laps = int(df["Lap"].max()) if "Lap" in df.columns else 58
            predicted = self._build_predicted_lap_times(df, compounds, total_laps)
            constraints = self._resolve_strategy_constraints(
                full_race_df, total_laps, max_pit_stops_input, min_stint_length_input
            )

            real_pit_counts = (
                full_race_df.dropna(subset=["Stint"]).groupby("Driver")["Stint"].max() - 1
            )
            target_pit_stops = (
                int(round(real_pit_counts.median())) if not real_pit_counts.empty else 1
            )
            target_pit_stops = max(1, min(target_pit_stops, constraints["max_pit_stops"]))

            params = Scope2Parameters(
                total_laps=total_laps,
                compounds=compounds,
                pit_loss_p=self._get_pit_loss_seconds(year, race_name),
                targets=GoalTargets(
                    target_race_time_t_star=scope1_target,
                    target_pit_stops_p_star=target_pit_stops,
                    target_degradation_d_star=0.4,
                ),
                weights=weights,
                max_pit_stops=constraints["max_pit_stops"],
                min_stint_length=constraints["min_stint_length"],
                max_stint_durability=self._get_max_stint_durability(
                    compounds,
                    race_df=full_race_df,
                    total_laps=total_laps,
                    max_stints=constraints["max_pit_stops"] + 1,
                ),
                predicted_lap_times=predicted,
                compound_degradations=self._get_compound_degradation_index(compounds),
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
                "pit_loss_seconds": params.pit_loss_p,
                "max_pit_stops": params.max_pit_stops,
                "min_stint_length": params.min_stint_length,
                "max_pit_stops_valid_range": constraints["max_pit_stops_valid_range"],
                "min_stint_length_valid_range": constraints["min_stint_length_valid_range"],
                "targets": {
                    "target_race_time_seconds": round(scope1_target, 2),
                    "target_pit_stops": target_pit_stops,
                    "target_degradation_index": params.targets.target_degradation_d_star,
                },
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
