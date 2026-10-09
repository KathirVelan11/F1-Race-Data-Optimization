"""Full-sweep validation: run Model 1 (MILP) and Model 2 (Goal Programming) across all
109 dry/3-compound races, each race using ONE random-but-feasible set of user inputs
(min_pit_stops, max_sets_per_compound, max_risk_tier_per_compound) shared by both models
so their outputs on a given race are directly comparable.

"Feasible" is computed from the SAME real per-race data the backend itself uses
(max_stint_durability, risk_tiers, min_stint_length) -- not guessed -- so randomized
inputs are deliberately kept inside the range the solver can actually satisfy, rather
than wasting runs on inputs we already know would be rejected.

Captures every field we might need afterwards (not just pass/fail): full strategy
sequences for both models, goal deviations, risk score, solve durations, and the exact
random inputs used per race, so this never needs to be rerun just to get one more field.

Usage:
    uv run python scripts/validate_models_random.py                  # all 109 races
    uv run python scripts/validate_models_random.py --seed 42         # reproducible run
    uv run python scripts/validate_models_random.py --years 2023 2024
    uv run python scripts/validate_models_random.py --resume

Writes scripts/validation_random_results.csv (flushed after every race, safe to Ctrl+C).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import pulp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.services.runner import BackendOptimizationRunner  # noqa: E402
from src.f1_optimizer.common.utils.time_utils import lap_time_str_to_seconds  # noqa: E402
from src.f1_optimizer.scope2.goals.goal_definitions import GoalTargets  # noqa: E402
from src.f1_optimizer.scope2.goals.weights import GoalWeights  # noqa: E402
from src.f1_optimizer.scope2.model.goal_model import Scope2GoalModel  # noqa: E402
from src.f1_optimizer.scope2.parameters.scope2_parameters import Scope2Parameters  # noqa: E402
from src.f1_optimizer.scope2.solver.goal_solver import Scope2GoalSolver  # noqa: E402


def filter_red_flag_laps(race: pd.DataFrame) -> pd.DataFrame:
    """Drop laps whose time is wildly inflated by a red flag / safety car stoppage (same
    3x-median-lap-time filter used in compare_to_real.py, reused so the real-driver
    baseline here is computed the identical way)."""
    median_lap = race["LapSeconds"].median()
    if pd.isna(median_lap) or median_lap <= 0:
        return race
    threshold = median_lap * 3
    return race[race["LapSeconds"].isna() | (race["LapSeconds"] <= threshold)]


def get_real_baseline(df: pd.DataFrame, year: int, race_name: str) -> dict | None:
    """Fastest driver who completed the full race distance (DNFs excluded), with their
    real strategy -- the ground-truth reference this validation sweep compares against."""
    race = df[(df["Year"] == year) & (df["Race"] == race_name)]
    if race.empty:
        return None

    race = filter_red_flag_laps(race)

    total_laps = race["Lap"].max()
    laps_completed = race.groupby("Driver")["Lap"].max()
    finishers = laps_completed[laps_completed >= total_laps - 1].index
    if len(finishers) == 0:
        return None

    finisher_totals = race[race["Driver"].isin(finishers)].groupby("Driver")["LapSeconds"].sum().dropna()
    if finisher_totals.empty:
        return None

    finisher_totals = finisher_totals.sort_values()
    fastest_driver = finisher_totals.index[0]
    fastest_time = float(finisher_totals.iloc[0])

    driver_df = race[race["Driver"] == fastest_driver].dropna(subset=["Stint", "Compound"])
    if driver_df.empty:
        stint_count = None
        compounds_used = ""
        detailed_strategy = ""
    else:
        stints = driver_df.groupby("Stint").agg(
            compound=("Compound", "first"),
            start_lap=("Lap", "min"),
            end_lap=("Lap", "max"),
        )
        stint_count = int(len(stints))
        compounds_used = "->".join(stints["compound"].tolist())
        # Same detailed (compound, start-end lap) format as the model strategies, so real
        # vs predicted can be compared stint-by-stint, not just by compound sequence.
        detailed_strategy = " -> ".join(
            f"{row.compound}({int(row.start_lap)}-{int(row.end_lap)})" for row in stints.itertuples()
        )

    # Data-quality signal: did the red-flag/safety-car lap filter actually remove
    # anything for this race? If so, the real baseline may still carry residual skew even
    # after filtering (same caveat the old compare_to_real.py artifact flagged).
    raw_race = df[(df["Year"] == year) & (df["Race"] == race_name)]
    red_flag_laps_dropped = int(len(raw_race) - len(race))

    return {
        "real_driver": fastest_driver,
        "real_time_seconds": round(fastest_time, 2),
        "real_pit_stops": (stint_count - 1) if stint_count else None,
        "real_strategy": compounds_used,
        "real_strategy_detailed": detailed_strategy,
        "real_stint_count": stint_count,
        "red_flag_laps_dropped": red_flag_laps_dropped,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Randomized-input validation sweep for Model 1 / Model 2.")
    parser.add_argument("--years", type=int, nargs="*", default=None, help="Restrict to these years.")
    parser.add_argument("--races", type=str, nargs="*", default=None, help="Restrict to these race names.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed, for a reproducible sweep.")
    parser.add_argument(
        "--out", type=str, default=str(Path(__file__).resolve().parent / "validation_random_results.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip races already present in --out (by year+race) and append new results instead of overwriting.",
    )
    parser.add_argument(
        "--workers", type=int, default=1,
        help=(
            "Number of races to run in parallel (separate processes). Races are "
            "fully independent of each other, so this does not change results, "
            "only wall-clock time. Default 1 (sequential, original behavior)."
        ),
    )
    return parser.parse_args()


def load_done_races(out_path: Path) -> set[tuple[int, str]]:
    if not out_path.exists():
        return set()
    done = set()
    with out_path.open("r", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                done.add((int(row["year"]), row["race"]))
            except (KeyError, ValueError):
                continue
    return done


def build_race_list(runner: BackendOptimizationRunner, args: argparse.Namespace) -> list[tuple[int, str]]:
    seasons = runner.get_dashboard_summary()["years"]
    if args.years:
        seasons = [y for y in seasons if y in args.years]

    cases: list[tuple[int, str]] = []
    for year in seasons:
        races = runner.get_races_for_season(year)
        if args.races:
            races = [r for r in races if r in args.races]
        for race in races:
            cases.append((year, race))

    if args.resume:
        done = load_done_races(Path(args.out))
        before = len(cases)
        cases = [c for c in cases if c not in done]
        print(f"Resume: {before - len(cases)} race(s) already in {args.out}, {len(cases)} remaining.")

    return cases


def generate_valid_inputs(
    runner: BackendOptimizationRunner,
    year: int,
    race: str,
    rng: random.Random,
) -> dict | None:
    """Pick one random-but-feasible input combo for this race, using the SAME helper
    methods the live backend uses to know what's actually valid -- no guessing, no
    retry-on-rejection. Returns None if the race itself has no usable data (e.g. empty).
    """
    full_race_df = runner.dataset_loader.get_race_dataframe(year, race)
    if full_race_df.empty:
        return None

    compounds = runner._get_available_compounds(full_race_df)
    if not compounds:
        return None
    total_laps = int(full_race_df["Lap"].max()) if "Lap" in full_race_df.columns else None
    if not total_laps:
        return None

    # min_stint_length: use the same data-driven default the backend would use with no
    # user override (requested_min_stint_length=None), so the rest of our math is
    # consistent with what the solver will actually enforce.
    base_constraints = runner._resolve_strategy_constraints(full_race_df, total_laps, None, None)
    min_stint_length = base_constraints["min_stint_length"]

    # min_pit_stops: randomized within a RACE-GROUNDED range, not a flat uniform [0,4] --
    # per user request, "min usually will be based on race". Mirrors the exact real
    # per-driver pit-count calculation _resolve_strategy_constraints uses for its UI hint
    # (10th percentile as a realistic floor, observed max as the ceiling), so every race's
    # range reflects what drivers actually did there, not a generic guess.
    real_pit_counts = full_race_df.dropna(subset=["Stint"]).groupby("Driver")["Stint"].max() - 1
    hint_default = max(1, int(real_pit_counts.quantile(0.1)) if not real_pit_counts.empty else 1)
    hint_upper = max(hint_default, int(real_pit_counts.max()) if not real_pit_counts.empty else 4, 1)

    max_feasible_stops = max(0, (total_laps // max(1, min_stint_length)) - 1)
    race_grounded_upper = min(hint_upper, max_feasible_stops)
    race_grounded_lower = min(hint_default, race_grounded_upper)
    min_pit_stops = rng.randint(race_grounded_lower, race_grounded_upper) if race_grounded_upper > 0 else 0
    stints_needed = min_pit_stops + 1

    max_stint_durability = runner._get_max_stint_durability(
        compounds, race_df=full_race_df, total_laps=total_laps, max_stints=stints_needed
    )
    risk_tiers = runner._get_degradation_risk_tiers(max_stint_durability)

    # max_risk_tier_per_compound: random tier per compound (3 = no limit, so simply
    # omitted), but only keep a restriction if its threshold is still >= min_stint_length
    # (otherwise that compound would be unusable at all, which isn't a useful test case
    # for "explore valid combinations").
    max_risk_tier_per_compound: dict[str, int] = {}
    for compound in compounds:
        tier = rng.randint(0, 3)
        if tier == 3:
            continue
        threshold = risk_tiers.get(compound, [0, 0, 0])[tier]
        if threshold >= min_stint_length:
            max_risk_tier_per_compound[compound] = tier

    # max_sets_per_compound: random 1-5 per compound, then scaled up if needed so the
    # total laps coverable (min(ceiling, durability) * sets, summed) >= total_laps --
    # computed directly rather than retried, so every race gets a usable combo.
    max_sets_per_compound: dict[str, int] = {compound: rng.randint(1, 5) for compound in compounds}

    def max_laps_per_set(compound: str) -> int:
        durability = max_stint_durability.get(compound, total_laps)
        ceiling_tier = max_risk_tier_per_compound.get(compound)
        if ceiling_tier is not None:
            return max(1, min(risk_tiers.get(compound, [0, 0, 0])[ceiling_tier], durability))
        return max(1, durability)

    def coverage() -> int:
        return sum(max_laps_per_set(c) * max_sets_per_compound[c] for c in compounds)

    # Also ensure the tyre-set feasibility rule (sum of sets >= stints_needed) holds.
    guard = 0
    while (coverage() < total_laps or sum(max_sets_per_compound.values()) < stints_needed) and guard < 50:
        compound = max(compounds, key=lambda c: max_laps_per_set(c))
        max_sets_per_compound[compound] += 1
        guard += 1

    # weights: randomized goal-priority weights (w1 time / w2 pit stops / w3 degradation),
    # normalized to sum to exactly 1.0 as GoalWeights requires -- per user request, so
    # Model 2 explores different trade-off preferences across races, not one fixed 50/25/25
    # split for all 109.
    raw = [rng.uniform(0.05, 1.0) for _ in range(3)]
    total_raw = sum(raw)
    weights = {
        "weight_time_w1": raw[0] / total_raw,
        "weight_pit_stops_w2": raw[1] / total_raw,
        "weight_degradation_w3": raw[2] / total_raw,
    }
    # Floating-point division can leave the sum a hair off 1.0 (e.g. 0.9999999999998) --
    # GoalWeights requires exact (within 1e-6), so fold the rounding error into w1 rather
    # than leave all three as raw divisions.
    weights["weight_time_w1"] = 1.0 - weights["weight_pit_stops_w2"] - weights["weight_degradation_w3"]

    # Feasibility retry: the coverage/tyre-set checks above guarantee ENOUGH laps are
    # coverable in total, but not that a valid STINT SEQUENCE exists under min_stint_length
    # + the risk ceilings together (e.g. a compound capped at 8 laps by its risk tier but
    # required to run >=10-lap stints by min_stint_length has zero usable stint lengths).
    # The only ground-truth check for that is the real R*-discovery solve itself, so probe
    # it directly and loosen the single tightest risk ceiling (or add a tyre set) on
    # failure, retrying with the real solver until it's genuinely feasible -- per user
    # request, every one of the 109 races should return a Model 2 result, not just most.
    max_feasibility_retries = 15
    for _ in range(max_feasibility_retries):
        probe_ok, probe_reason = _probe_risk_feasibility(
            total_laps=total_laps,
            compounds=compounds,
            min_pit_stops=min_pit_stops,
            min_stint_length=min_stint_length,
            max_stint_durability=max_stint_durability,
            max_sets_per_compound=max_sets_per_compound,
            risk_tiers=risk_tiers,
            max_risk_tier_per_compound=max_risk_tier_per_compound,
        )
        if probe_ok:
            break

        if max_risk_tier_per_compound:
            # Loosen the single tightest ceiling by one tier (or remove it at tier 2 -> no
            # limit) -- the most targeted fix, since the ceiling is almost always what's
            # actually blocking a valid stint sequence.
            tightest = min(max_risk_tier_per_compound, key=lambda c: max_risk_tier_per_compound[c])
            current_tier = max_risk_tier_per_compound[tightest]
            if current_tier >= 2:
                del max_risk_tier_per_compound[tightest]
            else:
                max_risk_tier_per_compound[tightest] = current_tier + 1
        else:
            # No risk ceilings left to loosen -- the remaining blocker is tyre-set count
            # vs. min_stint_length interaction, so add a set to whichever compound covers
            # the most laps per set (mirrors the coverage guard above).
            compound = max(compounds, key=lambda c: max_laps_per_set(c))
            max_sets_per_compound[compound] += 1
    else:
        # Exhausted retries (extremely rare) -- fall back to no risk ceilings at all, which
        # by construction (max_tier >= 3 means "no restriction") is always feasible.
        max_risk_tier_per_compound = {}

    return {
        "min_pit_stops": min_pit_stops,
        "min_stint_length": min_stint_length,
        "max_sets_per_compound": max_sets_per_compound,
        "max_risk_tier_per_compound": max_risk_tier_per_compound,
        "weights": weights,
        "compounds": compounds,
        "total_laps": total_laps,
        "risk_tiers": risk_tiers,
        "max_stint_durability": max_stint_durability,
    }


def _probe_risk_feasibility(
    total_laps: int,
    compounds: list[str],
    min_pit_stops: int,
    min_stint_length: int,
    max_stint_durability: dict[str, int],
    max_sets_per_compound: dict[str, int],
    risk_tiers: dict[str, list[int]],
    max_risk_tier_per_compound: dict[str, int],
) -> tuple[bool, str]:
    """Ground-truth feasibility check: actually runs the real R*-discovery MILP solve
    (the same one BackendOptimizationRunner._get_min_achievable_risk_score runs inside
    run_scope2) with these exact constraints, rather than approximating. Returns
    (True, "") if a minimum achievable risk score exists, else (False, reason)."""
    try:
        params = Scope2Parameters(
            total_laps=total_laps,
            compounds=compounds,
            pit_loss_p=25.0,  # irrelevant to a risk-only objective -- any positive value works
            targets=GoalTargets(target_race_time_t_star=1.0),
            weights=GoalWeights(),
            min_pit_stops=min_pit_stops,
            # Must match BackendOptimizationRunner._resolve_max_pit_stops' own default
            # EXACTLY (max(min_pit_stops, 1), used whenever the caller doesn't pass an
            # explicit max_pit_stops -- which run_one_race's payload never does) -- a
            # looser probe ceiling here previously made races look feasible that the real
            # run_scope2 call (forced to this tighter default) then rejected as Infeasible.
            max_pit_stops=max(min_pit_stops, 1),
            min_stint_length=min_stint_length,
            max_stint_durability=max_stint_durability,
            max_sets_per_compound=max_sets_per_compound,
            # Irrelevant to a risk-only objective (minimize_risk_only=True ignores lap-time
            # terms entirely) -- empty dicts are safe since the model only ever does
            # defaulting .get(..., 0.0) lookups against them.
            predicted_lap_times={},
            compound_base_pace={},
            compound_degradation_rate={},
            risk_tiers=risk_tiers,
            max_risk_tier_per_compound=max_risk_tier_per_compound,
        )
        model_builder = Scope2GoalModel(params, minimize_risk_only=True)
        model = model_builder.build()
        status = model.solve(Scope2GoalSolver()._build_solver())
        status_name = pulp.LpStatus[status]
        if status_name not in {"Optimal", "Not Solved"}:
            return False, status_name
        if pulp.value(model_builder.risk_score) is None:
            return False, "no value within time limit"
        return True, ""
    except Exception as exc:  # pragma: no cover - defensive: treat any probe error as infeasible
        return False, str(exc)


def strategy_to_str(strategy: list[dict]) -> str:
    return " -> ".join(f"{s['compound']}({s['start_lap']}-{s['end_lap']})" for s in strategy)


FIELDNAMES = [
    "year", "race", "total_laps", "compounds", "pit_loss_seconds_used",
    "min_pit_stops_used", "min_stint_length_used",
    "max_sets_per_compound_used", "max_risk_tier_per_compound_used", "risk_tiers_used",
    "max_stint_durability_used", "weights_used",
    # Real (ground truth)
    "real_driver", "real_time_seconds", "real_pit_stops", "real_stint_count",
    "real_strategy", "real_strategy_detailed", "red_flag_laps_dropped",
    # Model 1
    "m1_status", "m1_solve_seconds", "m1_race_time_seconds", "m1_pit_stop_count",
    "m1_strategy", "m1_message", "m1_delta_vs_real_seconds", "m1_faster_than_real",
    # Model 2
    "m2_status", "m2_solve_seconds", "m2_balanced_time_seconds", "m2_time_delta_vs_fastest",
    "m2_pit_stop_count", "m2_risk_score", "m2_strategy",
    "m2_d1_plus", "m2_d1_minus", "m2_d2_plus", "m2_d2_minus", "m2_d3_plus", "m2_d3_minus",
    "m2_objective_value_z", "m2_target_race_time", "m2_target_pit_stops", "m2_target_risk_score",
    "m2_message", "m2_delta_vs_real_seconds", "m2_faster_than_real",
]


def run_one_race(
    runner: BackendOptimizationRunner,
    full_dataset: pd.DataFrame,
    year: int,
    race: str,
    rng: random.Random,
) -> dict | None:
    inputs = generate_valid_inputs(runner, year, race, rng)
    if inputs is None:
        return None

    baseline = get_real_baseline(full_dataset, year, race) or {
        "real_driver": None, "real_time_seconds": None, "real_pit_stops": None,
        "real_stint_count": None, "real_strategy": "", "real_strategy_detailed": "",
        "red_flag_laps_dropped": None,
    }
    pit_loss_seconds = runner._get_pit_loss_seconds(year, race)

    payload = {
        "year": year,
        "race_name": race,
        "min_pit_stops": inputs["min_pit_stops"],
        "min_stint_length": inputs["min_stint_length"],
        "max_sets_per_compound": inputs["max_sets_per_compound"],
        "max_risk_tier_per_compound": inputs["max_risk_tier_per_compound"],
        "weights": inputs["weights"],
    }

    t0 = time.perf_counter()
    try:
        r1 = runner.run_scope1(payload)
    except Exception as exc:  # pragma: no cover - defensive
        r1 = {"strategy": [], "solver_status": None, "message": f"EXCEPTION: {exc}"}
    m1_elapsed = time.perf_counter() - t0

    t0 = time.perf_counter()
    try:
        r2 = runner.run_scope2(payload)
    except Exception as exc:  # pragma: no cover - defensive
        r2 = {"strategy": [], "solver_status": None, "message": f"EXCEPTION: {exc}"}
    # Retry once on a solver-reported "Infeasible" specifically (not other rejection
    # messages, e.g. the coverage-feasibility pre-check, which are genuinely deterministic).
    # Under N-way parallel workers competing for CPU, HiGHS can occasionally fail to find
    # ANY feasible incumbent within the time limit and report Infeasible even though the
    # problem is solvable -- confirmed by replaying a real sweep race standalone (no
    # contention) and getting "Best found" instead. A single retry gives it a second
    # independent attempt, which is enough in practice since the underlying problem IS
    # feasible; this never masks a genuine structural infeasibility, since those fail the
    # same way every time regardless of contention.
    if "Infeasible" in str(r2.get("message", "")):
        try:
            r2_retry = runner.run_scope2(payload)
            if "Infeasible" not in str(r2_retry.get("message", "")):
                r2 = r2_retry
        except Exception:
            pass  # keep the original r2 (and its message) if the retry itself errors
    m2_elapsed = time.perf_counter() - t0

    deviations = r2.get("deviations") or {}
    targets = r2.get("targets") or {}

    m1_time = r1.get("estimated_race_time_seconds")
    m2_time = r2.get("balanced_race_time_seconds")
    real_time = baseline["real_time_seconds"]

    m1_delta = round(float(m1_time) - real_time, 2) if (m1_time is not None and real_time is not None) else None
    m2_delta = round(float(m2_time) - real_time, 2) if (m2_time is not None and real_time is not None) else None

    return {
        "year": year,
        "race": race,
        "total_laps": inputs["total_laps"],
        "compounds": ";".join(inputs["compounds"]),
        "pit_loss_seconds_used": round(pit_loss_seconds, 2),
        "min_pit_stops_used": inputs["min_pit_stops"],
        "min_stint_length_used": inputs["min_stint_length"],
        "max_sets_per_compound_used": json.dumps(inputs["max_sets_per_compound"]),
        "max_risk_tier_per_compound_used": json.dumps(inputs["max_risk_tier_per_compound"]),
        "risk_tiers_used": json.dumps(inputs["risk_tiers"]),
        "max_stint_durability_used": json.dumps(inputs["max_stint_durability"]),
        "weights_used": json.dumps({k: round(v, 4) for k, v in inputs["weights"].items()}),
        "real_driver": baseline["real_driver"],
        "real_time_seconds": real_time,
        "real_pit_stops": baseline["real_pit_stops"],
        "real_stint_count": baseline["real_stint_count"],
        "real_strategy": baseline["real_strategy"],
        "real_strategy_detailed": baseline["real_strategy_detailed"],
        "red_flag_laps_dropped": baseline["red_flag_laps_dropped"],
        "m1_status": r1.get("solver_status"),
        "m1_solve_seconds": round(m1_elapsed, 2),
        "m1_race_time_seconds": m1_time,
        "m1_pit_stop_count": r1.get("pit_stop_count") or len(r1.get("pit_laps") or []),
        "m1_strategy": strategy_to_str(r1.get("strategy", [])),
        "m1_message": r1.get("message", ""),
        "m1_delta_vs_real_seconds": m1_delta,
        "m1_faster_than_real": (m1_delta < 0) if m1_delta is not None else None,
        "m2_status": r2.get("solver_status"),
        "m2_solve_seconds": round(m2_elapsed, 2),
        "m2_balanced_time_seconds": m2_time,
        "m2_time_delta_vs_fastest": r2.get("time_delta_vs_fastest_seconds"),
        "m2_pit_stop_count": r2.get("pit_stop_count"),
        "m2_risk_score": r2.get("risk_score"),
        "m2_strategy": strategy_to_str(r2.get("strategy", [])),
        "m2_d1_plus": deviations.get("d1_plus"),
        "m2_d1_minus": deviations.get("d1_minus"),
        "m2_d2_plus": deviations.get("d2_plus"),
        "m2_d2_minus": deviations.get("d2_minus"),
        "m2_d3_plus": deviations.get("d3_plus"),
        "m2_d3_minus": deviations.get("d3_minus"),
        "m2_objective_value_z": r2.get("objective_value_z"),
        "m2_target_race_time": targets.get("target_race_time_seconds"),
        "m2_target_pit_stops": targets.get("target_pit_stops"),
        "m2_target_risk_score": targets.get("target_risk_score"),
        "m2_message": r2.get("message", ""),
        "m2_delta_vs_real_seconds": m2_delta,
        "m2_faster_than_real": (m2_delta < 0) if m2_delta is not None else None,
    }


PROGRESS_EVERY = 10  # print an elapsed/ETA summary after every N races, per user request

# Per-process globals: each worker process builds its own runner and loads the dataset
# ONCE (in _worker_init), not once per race -- BackendOptimizationRunner and the
# dataframe aren't shared across processes, so each process needs its own copy anyway.
_worker_runner: BackendOptimizationRunner | None = None
_worker_dataset: pd.DataFrame | None = None


def _worker_init() -> None:
    global _worker_runner, _worker_dataset
    _worker_runner = BackendOptimizationRunner()
    _worker_dataset = pd.read_csv(Path(__file__).resolve().parent.parent / "data" / "processed" / "combined_dataset.csv")
    _worker_dataset["LapSeconds"] = _worker_dataset["LapTime"].map(lambda v: lap_time_str_to_seconds(str(v)))
    _worker_dataset["Compound"] = _worker_dataset["Compound"].astype(str).str.upper()


def _worker_run_one_race(year: int, race: str, seed_for_race: int) -> tuple[int, str, dict | None, float]:
    """Runs in a worker process. Builds its own RNG from a per-race seed (derived from the
    sweep's master seed, if any) so results stay reproducible regardless of worker count
    or which worker happens to pick up which race."""
    assert _worker_runner is not None and _worker_dataset is not None
    rng = random.Random(seed_for_race)
    t0 = time.perf_counter()
    row = run_one_race(_worker_runner, _worker_dataset, year, race, rng)
    elapsed = time.perf_counter() - t0
    return year, race, row, elapsed


def _emit_row(
    writer: "csv.DictWriter",
    fh,
    idx: int,
    total: int,
    year: int,
    race: str,
    row: dict | None,
    elapsed: float,
    counters: dict,
    start_all: float,
) -> None:
    """Shared per-race reporting/writing logic, used by both the sequential and
    parallel paths so progress output and CSV format stay identical either way."""
    if row is None:
        counters["skipped"] += 1
        print(f"[{idx}/{total}] {year} {race} -> SKIPPED (no usable race data)")
    else:
        writer.writerow(row)
        fh.flush()
        counters["completed"] += 1

        print(
            f"[{idx}/{total}] {year} {race} ({elapsed:.1f}s) "
            f"| inputs: pit>={row.get('min_pit_stops_used')} sets={row.get('max_sets_per_compound_used')} "
            f"risk_ceil={row.get('max_risk_tier_per_compound_used')} "
            f"| M1={row.get('m1_status')} t={row.get('m1_race_time_seconds')} "
            f"| M2={row.get('m2_status')} t={row.get('m2_balanced_time_seconds')} risk={row.get('m2_risk_score')} "
            f"| real={row.get('real_time_seconds')} ({row.get('real_driver')})"
        )
        if row.get("m1_message") and "successfully" not in str(row["m1_message"]).lower() and row.get("m1_status"):
            print(f"    M1 note: {row['m1_message']}")
        if row.get("m2_message") and "successfully" not in str(row["m2_message"]).lower():
            print(f"    M2 note: {row['m2_message']}")

    if idx % PROGRESS_EVERY == 0 or idx == total:
        elapsed_total = time.perf_counter() - start_all
        avg_per_race = elapsed_total / idx
        remaining = total - idx
        eta_seconds = avg_per_race * remaining
        print(
            f"\n----- Progress: {idx}/{total} races done "
            f"({counters['completed']} ok, {counters['skipped']} skipped, {counters['errored']} errored) -----\n"
            f"      Elapsed: {elapsed_total / 60:.1f} min "
            f"| Avg/race: {avg_per_race:.1f}s "
            f"| Est. remaining: {eta_seconds / 60:.1f} min "
            f"({remaining} races left)\n"
        )


def main() -> None:
    args = parse_args()
    master_rng = random.Random(args.seed)
    runner = BackendOptimizationRunner()
    cases = build_race_list(runner, args)

    # Derive one reproducible per-race seed from the master seed up front (both the
    # sequential and parallel paths use this), so a given race gets the same randomized
    # inputs regardless of --workers or which worker happens to pick it up.
    race_seeds = [master_rng.randrange(2**31) for _ in cases]

    print(f"Validating {len(cases)} race(s) with randomized-but-feasible inputs (seed={args.seed}, workers={args.workers})...")
    print(f"Progress summary every {PROGRESS_EVERY} races. Safe to interrupt (Ctrl+C) -- results are flushed to disk after every race.\n")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    append_mode = args.resume and out_path.exists()

    counters = {"completed": 0, "skipped": 0, "errored": 0}
    start_all = time.perf_counter()

    with out_path.open("a" if append_mode else "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        if not append_mode:
            writer.writeheader()
        fh.flush()

        if args.workers <= 1:
            print("Loading full dataset for real-driver baseline lookups...")
            full_dataset = pd.read_csv(Path(__file__).resolve().parent.parent / "data" / "processed" / "combined_dataset.csv")
            full_dataset["LapSeconds"] = full_dataset["LapTime"].map(lambda v: lap_time_str_to_seconds(str(v)))
            full_dataset["Compound"] = full_dataset["Compound"].astype(str).str.upper()

            try:
                for idx, ((year, race), seed_for_race) in enumerate(zip(cases, race_seeds), start=1):
                    rng = random.Random(seed_for_race)
                    t0 = time.perf_counter()
                    try:
                        row = run_one_race(runner, full_dataset, year, race, rng)
                    except Exception as exc:  # pragma: no cover - defensive: never let one
                        # race's unexpected failure kill the whole sweep. Both models are
                        # already individually try/excepted inside run_one_race -- this is
                        # the outer safety net for anything else (e.g. generate_valid_inputs
                        # itself raising), so every race still gets a row on disk.
                        row = {name: "" for name in FIELDNAMES}
                        row.update({"year": year, "race": race, "m1_message": f"SWEEP EXCEPTION: {exc}"})
                        counters["errored"] += 1
                        print(f"[{idx}/{len(cases)}] {year} {race} -> ERROR: {exc}")
                    elapsed = time.perf_counter() - t0
                    _emit_row(writer, fh, idx, len(cases), year, race, row, elapsed, counters, start_all)
            except KeyboardInterrupt:
                print(f"\nInterrupted after {counters['completed']}/{len(cases)} race(s). Partial report saved.")
        else:
            # Races are fully independent of each other (each builds its own strategy
            # from scratch), so running them in separate processes changes only
            # wall-clock time, never results. Each worker process builds its own
            # BackendOptimizationRunner + loads the dataset ONCE (_worker_init), not
            # once per race.
            try:
                with ProcessPoolExecutor(max_workers=args.workers, initializer=_worker_init) as pool:
                    futures = {
                        pool.submit(_worker_run_one_race, year, race, seed_for_race): (year, race)
                        for (year, race), seed_for_race in zip(cases, race_seeds)
                    }
                    # Completion order is whatever finishes first, not submission order --
                    # idx here just counts "how many done so far" for progress reporting.
                    for idx, future in enumerate(as_completed(futures), start=1):
                        year, race = futures[future]
                        try:
                            _, _, row, elapsed = future.result()
                        except Exception as exc:  # pragma: no cover - defensive
                            row = {name: "" for name in FIELDNAMES}
                            row.update({"year": year, "race": race, "m1_message": f"SWEEP EXCEPTION: {exc}"})
                            elapsed = 0.0
                            counters["errored"] += 1
                            print(f"[{idx}/{len(cases)}] {year} {race} -> ERROR: {exc}")
                        _emit_row(writer, fh, idx, len(cases), year, race, row, elapsed, counters, start_all)
            except KeyboardInterrupt:
                print(f"\nInterrupted after {counters['completed']}/{len(cases)} race(s). Partial report saved.")

    total_elapsed = time.perf_counter() - start_all
    print(f"\n{'=' * 60}")
    print(f"Finished {counters['completed']} race(s) ({counters['skipped']} skipped, {counters['errored']} errored) in {total_elapsed / 60:.1f} min.")
    print(f"Report written to: {out_path}")


if __name__ == "__main__":
    main()
