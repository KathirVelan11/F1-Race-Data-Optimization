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
        self._compound_degradation_rate_cache: Optional[Dict[str, float]] = None
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
        requested_min_pit_stops: Optional[int] = None,
        requested_min_stint_length: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Resolve min_pit_stops / min_stint_length from optional user input.

        min_pit_stops follows the same exact-value rule as max_sets_per_compound: the
        user's entered value is used exactly (clamped only to be non-negative), and
        blank means 0 (no minimum pit-stop requirement). There is no data-driven default
        and no silent clamping -- if the entered value turns out to be infeasible given
        the race's other constraints (tyre sets, durability), that surfaces as a clear
        rejection rather than being quietly adjusted.

        min_stint_length keeps its original data-driven-default behavior (defaults to the
        race's real 5th-percentile stint length when blank, clamped to a valid range when
        entered) -- that part of the design wasn't changed.

        `valid_range` for min_pit_stops is informational only (a hint derived from real
        per-driver pit counts in this race), not an enforced bound.
        """
        stint_lengths = (
            race_df.dropna(subset=["Stint", "TyreLife"])
            .groupby(["Driver", "Stint"])["TyreLife"]
            .max()
        )
        real_pit_counts = (
            race_df.dropna(subset=["Stint"]).groupby("Driver")["Stint"].max() - 1
        )

        # Informational hint range only -- real per-driver pit counts observed in this race.
        hint_default = max(1, int(real_pit_counts.quantile(0.1)) if not real_pit_counts.empty else 1)
        hint_upper = max(hint_default, int(real_pit_counts.max()) if not real_pit_counts.empty else 4, 1)

        min_pit_stops = max(0, int(requested_min_pit_stops)) if requested_min_pit_stops is not None else 0

        # Min stint length: default to a conservative floor below which almost no real
        # stint falls (5th percentile), never above what total_laps/stint-count allows.
        observed_min = int(stint_lengths.quantile(0.05)) if not stint_lengths.empty else 3
        default_min_stint_length = max(1, min(observed_min, 5))
        upper_bound_stint_length = max(1, total_laps // max(1, min_pit_stops + 1))
        if requested_min_stint_length is None:
            min_stint_length = min(default_min_stint_length, upper_bound_stint_length)
        else:
            min_stint_length = max(1, min(int(requested_min_stint_length), upper_bound_stint_length))

        return {
            "min_pit_stops": min_pit_stops,
            "min_stint_length": min_stint_length,
            "min_pit_stops_valid_range": [0, hint_upper],
            "min_stint_length_valid_range": [1, upper_bound_stint_length],
        }

    @staticmethod
    def _resolve_max_sets_per_compound(
        race_df: "pd.DataFrame",
        compounds: List[str],
        min_pit_stops: int,
        requested: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Resolve how many separate stints (tyre sets) are allowed per compound.

        Real F1 teams have a limited allocation of each compound for a race weekend --
        this models that as a per-compound cap on stint count. The user's entered value is
        used exactly as given (clamped only to be non-negative -- a negative set count is
        meaningless); a compound the user left blank is treated as 0 sets available, i.e.
        that compound cannot be used at all. There is no silent auto-correction: if the
        entered counts can't cover the race (too few total stints for min_pit_stops+1,
        the minimum number of stints a strategy meeting the pit-stop floor requires), that
        surfaces as a clear rejection rather than being quietly bumped up.

        `valid_ranges` is informational only (shown in the UI as a hint derived from real
        per-driver stint counts on that compound in this race) -- it does not constrain
        what the user can actually enter.
        """
        stints_per_compound_driver = (
            race_df.dropna(subset=["Stint", "Compound"])
            .assign(Compound=lambda d: d["Compound"].astype(str).str.upper())
            .groupby(["Driver", "Compound"])["Stint"]
            .nunique()
        )

        total_stints_needed = min_pit_stops + 1
        resolved: Dict[str, int] = {}
        valid_ranges: Dict[str, List[int]] = {}

        for compound in compounds:
            real_counts = stints_per_compound_driver.xs(compound, level="Compound", drop_level=True) \
                if compound in stints_per_compound_driver.index.get_level_values("Compound") else None
            hint_default = max(1, int(real_counts.quantile(0.9)) if real_counts is not None and not real_counts.empty else 2)
            hint_upper = max(hint_default, total_stints_needed, int(real_counts.max()) if real_counts is not None and not real_counts.empty else total_stints_needed)
            valid_ranges[compound] = [1, hint_upper]

            requested_value = (requested or {}).get(compound)
            resolved[compound] = max(0, int(requested_value)) if requested_value is not None else 0

        return {
            "max_sets_per_compound": resolved,
            "max_sets_per_compound_valid_range": valid_ranges,
            "max_sets_per_compound_feasible": sum(resolved.values()) >= total_stints_needed,
        }

    @staticmethod
    def _resolve_max_risk_tier_per_compound(
        compounds: List[str],
        requested: Optional[Dict[str, int]] = None,
    ) -> Dict[str, int]:
        """Resolve the user's optional per-compound max acceptable degradation-risk tier
        (0=low, 1=moderate, 2=high, 3=very high -- see _get_degradation_risk_tiers).

        This is a genuine hard ceiling enforced in Scope2GoalModel (le_k forced to 1 for
        all laps beyond the chosen tier), not a soft preference. A compound the user
        didn't set, or set to 3 (very high / "no limit"), is simply left out of the
        returned dict -- Scope2GoalModel only restricts compounds present in it.
        Out-of-range values are clamped into [0, 3] rather than rejected, since a
        ceiling is a UI convenience, not a safety-critical input worth a hard error.
        """
        resolved: Dict[str, int] = {}
        for compound in compounds:
            requested_value = (requested or {}).get(compound)
            if requested_value is None:
                continue
            tier = max(0, min(3, int(requested_value)))
            if tier < 3:
                resolved[compound] = tier
        return resolved

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

        `max_stints` is min_pit_stops + 1, the minimum stint count the solver's chosen
        strategy will have (which may be user-supplied) -- the floor below must cover at
        least that many stints, otherwise a durability guarantee sized too small can make
        the solver infeasible when the user requires more stops (less room per stint).
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

    @staticmethod
    def _get_degradation_risk_tiers(max_stint_durability: Dict[str, int]) -> Dict[str, List[int]]:
        """Per-compound tyre-age thresholds for the 4 degradation-risk tiers (0=low,
        1=moderate, 2=high, 3=very high), scaled to that compound's own real durability
        rather than a fixed age cutoff -- a compound that durably lasts 40 laps and one
        that lasts 20 reach the same relative wear state at different absolute ages.

        Tried fitting these boundaries directly from lap-time-vs-tyre-age data (both raw
        and stint-relative); neither showed a usable monotonic signal in this dataset
        (confounded by fuel burn-off, traffic, SC periods) -- so the tier split itself
        (40%/70%/90% of durability) is a physically reasonable choice, not a data fit.

        Returns {compound: [t1, t2, t3]} where tyre age <= t1 is low risk, <= t2 is
        moderate, <= t3 is high, and above t3 is very high.
        """
        tiers: Dict[str, List[int]] = {}
        for compound, durability in max_stint_durability.items():
            t1 = max(1, round(durability * 0.4))
            t2 = max(t1 + 1, round(durability * 0.7))
            t3 = max(t2 + 1, round(durability * 0.9))
            tiers[compound] = [t1, t2, t3]
        return tiers

    def _build_predicted_lap_times(
        self, df: "pd.DataFrame", compounds: List[str], total_laps: int
    ) -> Dict[int, Dict[str, float]]:
        """Predicted lap time per (lap, compound) from the fitted degradation model only:
        base_pace[compound] + degradation_rate[compound] * lap. Both are fit from this
        race's own real data (falling back to dataset-wide where this race lacks enough
        data -- see _get_compound_base_pace / _get_compound_degradation_rate), so the
        curve is race-specific, but raw per-lap real averages are never used directly --
        they're noisy (fuel load, traffic, SC laps), so the smooth fitted curve is used
        everywhere for consistency."""
        base_pace = self._get_compound_base_pace(compounds, race_df=df)
        degradation_rate = self._get_compound_degradation_rate(compounds, race_df=df)
        lap_times: Dict[int, Dict[str, float]] = {}

        for lap in range(1, total_laps + 1):
            lap_times[lap] = {
                compound: base_pace[compound] + degradation_rate[compound] * lap
                for compound in compounds
            }

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

    def _get_compound_base_pace(
        self, compounds: List[str], race_df: Optional["pd.DataFrame"] = None
    ) -> Dict[str, float]:
        """Mean lap time (seconds) per compound, preferring this specific race's own real
        laps (lap time is dominated by circuit length/layout, e.g. Monaco ~82s vs a
        global SOFT average of ~97s pooled across every circuit), falling back to the
        dataset-wide mean per compound, and only then to the dataset-wide mean across all
        compounds for a compound with no data anywhere."""
        if self._compound_base_pace_cache is None:
            full_df = self.dataset_loader.load_dataset()
            df = full_df.copy()
            df["Compound"] = df["Compound"].astype(str).str.upper()
            df["LapSeconds"] = df["LapTime"].map(lambda value: lap_time_str_to_seconds(str(value)))
            df = df.dropna(subset=["LapSeconds"])
            df = df[~df["Compound"].isin(EXCLUDED_COMPOUNDS)]
            self._compound_base_pace_cache = df.groupby("Compound")["LapSeconds"].mean().to_dict()

        race_pace: Dict[str, float] = {}
        if race_df is not None and not race_df.empty:
            race = race_df.copy()
            race["Compound"] = race["Compound"].astype(str).str.upper()
            race["LapSeconds"] = race["LapTime"].map(lambda value: lap_time_str_to_seconds(str(value)))
            race = race.dropna(subset=["LapSeconds"])
            race = race[~race["Compound"].isin(EXCLUDED_COMPOUNDS)]
            race_pace = race.groupby("Compound")["LapSeconds"].mean().to_dict()

        dataset_wide_fallback = (
            float(sum(self._compound_base_pace_cache.values()) / len(self._compound_base_pace_cache))
            if self._compound_base_pace_cache else 90.0
        )
        return {
            compound: float(
                race_pace.get(compound, self._compound_base_pace_cache.get(compound, dataset_wide_fallback))
            )
            for compound in compounds
        }

    def _get_compound_degradation_rate(
        self, compounds: List[str], race_df: Optional["pd.DataFrame"] = None
    ) -> Dict[str, float]:
        """Real degradation rate (seconds lost per lap of tyre age) per compound, fit from
        actual lap-time-vs-TyreLife data instead of an assumed formula.

        Prefers this race's own data (circuit-specific wear characteristics, e.g. Monaco's
        low-speed laps wear tyres far more slowly than a high-speed circuit), falling back
        to the dataset-wide fit per compound, and finally to 0.0 (flat, no assumed
        degradation) only if a compound has no tyre-age data anywhere -- never a guessed
        slope.
        """
        if self._compound_degradation_rate_cache is None:
            full_df = self.dataset_loader.load_dataset()
            self._compound_degradation_rate_cache = self._fit_degradation_rates(full_df)

        race_rates: Dict[str, float] = {}
        if race_df is not None and not race_df.empty:
            race_rates = self._fit_degradation_rates(race_df)

        return {
            compound: race_rates.get(
                compound, self._compound_degradation_rate_cache.get(compound, 0.0)
            )
            for compound in compounds
        }

    @staticmethod
    def _fit_degradation_rates(race_df: "pd.DataFrame") -> Dict[str, float]:
        """Per compound: slope of a linear fit of LapSeconds vs TyreLife, clamped to >= 0
        (a compound cannot get faster as it wears; a negative raw fit means the signal is
        dominated by fuel burn-off/traffic rather than tyre wear, so it's floored at 0
        rather than reporting a physically backwards number)."""
        df = race_df.copy()
        df["Compound"] = df["Compound"].astype(str).str.upper()
        df["LapSeconds"] = df["LapTime"].map(lambda value: lap_time_str_to_seconds(str(value)))
        df = df.dropna(subset=["LapSeconds", "TyreLife"])
        df = df[~df["Compound"].isin(EXCLUDED_COMPOUNDS)]

        rates: Dict[str, float] = {}
        for compound, group in df.groupby("Compound"):
            if len(group) < 5 or group["TyreLife"].nunique() < 2:
                continue
            slope = group["TyreLife"].cov(group["LapSeconds"]) / group["TyreLife"].var()
            if pd.isna(slope):
                continue
            rates[compound] = round(max(float(slope), 0.0), 4)
        return rates

    @staticmethod
    def _get_target_risk_score(race_df: "pd.DataFrame", risk_tiers: Dict[str, List[int]]) -> float:
        """Real target risk score R* for this race: the actual degradation-risk score of
        real drivers' real stints, using their real recorded TyreLife (tyre age) against
        the risk tiers. Computed per (driver, stint), then averaged across drivers, so R*
        reflects what real strategies in this race actually incurred -- mirrors how
        target_pit_stops is derived from the real median pit count rather than a guess.
        """
        stints = race_df.dropna(subset=["Stint", "Compound", "TyreLife"]).copy()
        stints["Compound"] = stints["Compound"].astype(str).str.upper()
        if stints.empty:
            return 1.0

        max_age_per_stint = (
            stints.groupby(["Driver", "Stint", "Compound"])["TyreLife"].max().reset_index()
        )

        def risk_for_age(compound: str, age: float) -> int:
            t1, t2, t3 = risk_tiers.get(compound, [10, 20, 30])
            if age <= t1:
                return 0
            if age <= t2:
                return 1
            if age <= t3:
                return 2
            return 3

        max_age_per_stint["risk"] = max_age_per_stint.apply(
            lambda row: risk_for_age(row["Compound"], row["TyreLife"]), axis=1
        )
        per_driver_total_risk = max_age_per_stint.groupby("Driver")["risk"].sum()
        if per_driver_total_risk.empty:
            return 1.0
        return round(float(per_driver_total_risk.mean()), 3)

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
        min_pit_stops: Optional[int] = None,
        min_stint_length: Optional[int] = None,
        max_sets_per_compound: Optional[Dict[str, int]] = None,
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
            full_race_df, total_laps, min_pit_stops, min_stint_length
        )
        sets_constraints = self._resolve_max_sets_per_compound(
            full_race_df, compounds, constraints["min_pit_stops"], max_sets_per_compound
        )
        constraints.update(sets_constraints)

        parameters = Scope1Parameters(
            total_laps=total_laps,
            compounds=compounds,
            pit_loss_p=self._get_pit_loss_seconds(year, race_name),
            min_pit_stops=constraints["min_pit_stops"],
            min_stint_length=constraints["min_stint_length"],
            max_stint_durability=self._get_max_stint_durability(
                compounds,
                race_df=full_race_df,
                total_laps=total_laps,
                max_stints=constraints["min_pit_stops"] + 1,
            ),
            max_sets_per_compound=constraints["max_sets_per_compound"],
            predicted_lap_times=lap_times_by_compound,
        )
        return parameters, constraints

    def build_strategy_preview(
        self,
        year: int,
        race_name: str,
        driver_code: Optional[str] = None,
        min_pit_stops: Optional[int] = None,
        min_stint_length: Optional[int] = None,
        max_sets_per_compound: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Return a real Scope 1 strategy preview for the frontend."""
        try:
            parameters, constraints = self._build_scope1_parameters(
                year, race_name, driver_code, min_pit_stops, min_stint_length, max_sets_per_compound
            )
            if not constraints["max_sets_per_compound_feasible"]:
                total_sets = sum(parameters.max_sets_per_compound.values())
                stints_needed = parameters.min_pit_stops + 1
                return {
                    "year": year,
                    "race_name": race_name,
                    "driver_code": driver_code,
                    "strategy": [],
                    "max_sets_per_compound": parameters.max_sets_per_compound,
                    "max_sets_per_compound_valid_range": constraints["max_sets_per_compound_valid_range"],
                    "message": (
                        f"Not enough tyre sets entered: {total_sets} total across "
                        f"{', '.join(parameters.compounds)}, but this strategy needs at "
                        f"least {stints_needed} stints (min_pit_stops={parameters.min_pit_stops} + 1). "
                        "Increase one or more compound set counts, or lower min pit stops."
                    ),
                }
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
                "min_pit_stops": parameters.min_pit_stops,
                "min_stint_length": parameters.min_stint_length,
                "min_pit_stops_valid_range": constraints["min_pit_stops_valid_range"],
                "min_stint_length_valid_range": constraints["min_stint_length_valid_range"],
                "max_sets_per_compound": parameters.max_sets_per_compound,
                "max_sets_per_compound_valid_range": constraints["max_sets_per_compound_valid_range"],
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
        min_pit_stops = request_data.get("min_pit_stops")
        min_stint_length = request_data.get("min_stint_length")
        max_sets_per_compound = request_data.get("max_sets_per_compound")
        return self.build_strategy_preview(
            year, race_name, driver_code, min_pit_stops, min_stint_length, max_sets_per_compound
        )

    def run_scope2(self, request_data: Any) -> Any:
        """Solve the Scope 2 goal-programming model for the selected race."""
        year = int(request_data.get("year", 2024))
        race_name = str(request_data.get("race_name", "Australian Grand Prix"))
        driver_code = request_data.get("driver_code")
        min_pit_stops_input = request_data.get("min_pit_stops")
        min_stint_length_input = request_data.get("min_stint_length")
        max_sets_per_compound_input = request_data.get("max_sets_per_compound")
        max_risk_tier_input = request_data.get("max_risk_tier_per_compound")

        try:
            scope1 = self.build_strategy_preview(
                year, race_name, driver_code, min_pit_stops_input, min_stint_length_input, max_sets_per_compound_input
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
                full_race_df, total_laps, min_pit_stops_input, min_stint_length_input
            )
            sets_constraints = self._resolve_max_sets_per_compound(
                full_race_df, compounds, constraints["min_pit_stops"], max_sets_per_compound_input
            )
            constraints.update(sets_constraints)

            if not constraints["max_sets_per_compound_feasible"]:
                total_sets = sum(sets_constraints["max_sets_per_compound"].values())
                stints_needed = constraints["min_pit_stops"] + 1
                return {
                    "year": year,
                    "race_name": race_name,
                    "driver_code": driver_code,
                    "strategy": [],
                    "max_sets_per_compound": sets_constraints["max_sets_per_compound"],
                    "max_sets_per_compound_valid_range": sets_constraints["max_sets_per_compound_valid_range"],
                    "message": (
                        f"Not enough tyre sets entered: {total_sets} total across "
                        f"{', '.join(compounds)}, but this strategy needs at least "
                        f"{stints_needed} stints (min_pit_stops={constraints['min_pit_stops']} + 1). "
                        "Increase one or more compound set counts, or lower min pit stops."
                    ),
                }

            real_pit_counts = (
                full_race_df.dropna(subset=["Stint"]).groupby("Driver")["Stint"].max() - 1
            )
            target_pit_stops = (
                int(round(real_pit_counts.median())) if not real_pit_counts.empty else 1
            )
            target_pit_stops = max(target_pit_stops, constraints["min_pit_stops"])

            max_stint_durability = self._get_max_stint_durability(
                compounds,
                race_df=full_race_df,
                total_laps=total_laps,
                max_stints=constraints["min_pit_stops"] + 1,
            )
            risk_tiers = self._get_degradation_risk_tiers(max_stint_durability)
            target_risk = self._get_target_risk_score(full_race_df, risk_tiers)
            max_risk_tier_per_compound = self._resolve_max_risk_tier_per_compound(
                compounds, max_risk_tier_input
            )

            # A requested risk ceiling can make the compound physically unusable if its
            # tier threshold is smaller than the minimum stint length (no valid stint
            # could ever stay within the ceiling) -- surface that as a clear rejection
            # rather than handing an infeasible model to the solver.
            infeasible_ceilings = []
            for compound, max_tier in max_risk_tier_per_compound.items():
                tier_threshold = risk_tiers.get(compound, [0, 0, 0])[max_tier]
                if tier_threshold < constraints["min_stint_length"]:
                    infeasible_ceilings.append(
                        f"{compound} (ceiling allows age<={tier_threshold}, "
                        f"but min stint length is {constraints['min_stint_length']})"
                    )
            if infeasible_ceilings:
                return {
                    "year": year,
                    "race_name": race_name,
                    "driver_code": driver_code,
                    "strategy": [],
                    "max_risk_tier_per_compound": max_risk_tier_per_compound,
                    "message": (
                        "Risk ceiling too strict for: " + "; ".join(infeasible_ceilings) +
                        ". Raise the allowed risk tier for that compound, or lower min stint length."
                    ),
                }

            params = Scope2Parameters(
                total_laps=total_laps,
                compounds=compounds,
                pit_loss_p=self._get_pit_loss_seconds(year, race_name),
                targets=GoalTargets(
                    target_race_time_t_star=scope1_target,
                    target_pit_stops_p_star=target_pit_stops,
                    target_degradation_d_star=target_risk,
                ),
                weights=weights,
                min_pit_stops=constraints["min_pit_stops"],
                min_stint_length=constraints["min_stint_length"],
                max_stint_durability=max_stint_durability,
                max_sets_per_compound=constraints["max_sets_per_compound"],
                predicted_lap_times=predicted,
                risk_tiers=risk_tiers,
                max_risk_tier_per_compound=max_risk_tier_per_compound,
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
                "risk_score": round(result.risk_score, 2),
                "objective_value_z": round(result.objective_value_z, 4),
                "solver_status": result.solver_status,
                "pit_loss_seconds": params.pit_loss_p,
                "min_pit_stops": params.min_pit_stops,
                "min_stint_length": params.min_stint_length,
                "min_pit_stops_valid_range": constraints["min_pit_stops_valid_range"],
                "min_stint_length_valid_range": constraints["min_stint_length_valid_range"],
                "max_sets_per_compound": params.max_sets_per_compound,
                "max_sets_per_compound_valid_range": constraints["max_sets_per_compound_valid_range"],
                "risk_tiers": risk_tiers,
                "max_risk_tier_per_compound": params.max_risk_tier_per_compound,
                "targets": {
                    "target_race_time_seconds": round(scope1_target, 2),
                    "target_pit_stops": target_pit_stops,
                    "target_risk_score": params.targets.target_degradation_d_star,
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
