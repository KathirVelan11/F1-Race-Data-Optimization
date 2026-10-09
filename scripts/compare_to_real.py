"""Compare Model 1 / Model 2 predictions against the real race outcome.

For each race in scripts/validation_report.csv, re-solves both models (to capture the
full predicted stint/compound sequence, not just counts) and finds the fastest driver
who finished the real race distance (excludes DNFs/retirements), then compares:
  - real total race time vs predicted race time
  - real strategy (stint/compound sequence, pit stop count) vs predicted strategy

Usage:
    uv run python scripts/compare_to_real.py
    uv run python scripts/compare_to_real.py --resume
    uv run python scripts/compare_to_real.py --out scripts/real_vs_predicted.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.services.runner import BackendOptimizationRunner  # noqa: E402
from src.f1_optimizer.common.utils.time_utils import lap_time_str_to_seconds  # noqa: E402

FIELDNAMES = [
    "year", "race", "model", "real_driver", "real_time_seconds", "real_pit_stops",
    "real_strategy", "predicted_time_seconds", "predicted_pit_stops", "predicted_strategy",
    "delta_seconds", "faster_than_real", "outlier",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare model predictions against real race results.")
    parser.add_argument(
        "--validation-csv", type=str,
        default=str(Path(__file__).resolve().parent / "validation_report.csv"),
    )
    parser.add_argument(
        "--out", type=str,
        default=str(Path(__file__).resolve().parent / "real_vs_predicted.csv"),
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip (year, race) pairs already fully present (both models) in --out.",
    )
    parser.add_argument(
        "--skip", type=str, nargs="*", default=[],
        help="Race names to skip entirely (e.g. races where CBC hangs indefinitely).",
    )
    return parser.parse_args()


def filter_red_flag_laps(race: pd.DataFrame) -> pd.DataFrame:
    """Drop laps whose time is wildly inflated by a red flag / safety car stoppage.

    The raw dataset records stoppage time as part of whatever lap was in progress, which
    can turn a ~90s lap into a 3000+s "lap". Capped at 3x the race's own median lap time,
    which comfortably covers normal variance while catching true stoppage laps.
    """
    median_lap = race["LapSeconds"].median()
    if pd.isna(median_lap) or median_lap <= 0:
        return race
    threshold = median_lap * 3
    return race[race["LapSeconds"].isna() | (race["LapSeconds"] <= threshold)]


def get_real_baseline(df: pd.DataFrame, year: int, race_name: str) -> dict | None:
    """Fastest driver who completed the full race distance, with their real strategy."""
    race = df[(df["Year"] == year) & (df["Race"] == race_name)]
    if race.empty:
        return None

    race = filter_red_flag_laps(race)

    total_laps = race["Lap"].max()
    laps_completed = race.groupby("Driver")["Lap"].max()
    finishers = laps_completed[laps_completed >= total_laps - 1].index
    if len(finishers) == 0:
        return None

    finisher_totals = (
        race[race["Driver"].isin(finishers)].groupby("Driver")["LapSeconds"].sum().dropna()
    )
    if finisher_totals.empty:
        return None

    finisher_totals = finisher_totals.sort_values()
    fastest_driver = finisher_totals.index[0]
    fastest_time = float(finisher_totals.iloc[0])

    driver_df = race[race["Driver"] == fastest_driver].dropna(subset=["Stint", "Compound"])
    if driver_df.empty:
        stint_count = None
        compounds_used = ""
    else:
        stints = driver_df.groupby("Stint").agg(compound=("Compound", "first"))
        stint_count = int(len(stints))
        compounds_used = "->".join(stints["compound"].tolist())

    return {
        "real_driver": fastest_driver,
        "real_time_seconds": round(fastest_time, 2),
        "real_stint_count": stint_count,
        "real_pit_stops": (stint_count - 1) if stint_count else None,
        "real_strategy": compounds_used,
    }


def strategy_string(result: dict) -> str:
    """Render a solver result's stint list as a compound sequence, e.g. SOFT->MEDIUM->HARD."""
    strategy = result.get("strategy") or []
    return "->".join(stage["compound"] for stage in strategy)


def load_done_pairs(out_path: Path) -> set[tuple[int, str]]:
    """(year, race) pairs that already have both models present in an existing report."""
    if not out_path.exists():
        return set()
    seen: dict[tuple[int, str], set[str]] = {}
    with out_path.open("r", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                key = (int(row["year"]), row["race"])
            except (KeyError, ValueError):
                continue
            seen.setdefault(key, set()).add(row["model"])
    return {key for key, models in seen.items() if {"Model1_MILP", "Model2_GoalProgramming"} <= models}


def main() -> None:
    args = parse_args()

    validation_path = Path(args.validation_csv)
    if not validation_path.exists():
        print(f"Validation report not found at {validation_path}. Run validate_models.py first.")
        sys.exit(1)

    validated = pd.read_csv(validation_path)
    validated = validated[validated["ok"] == True]  # noqa: E712
    races = validated[["year", "race"]].drop_duplicates()
    races = list(races.itertuples(index=False, name=None))

    out_path = Path(args.out)
    if args.resume:
        done = load_done_pairs(out_path)
        before = len(races)
        races = [(y, r) for y, r in races if (int(y), r) not in done]
        print(f"Resume: {before - len(races)} race(s) already done, {len(races)} remaining.")

    if args.skip:
        before = len(races)
        races = [(y, r) for y, r in races if r not in args.skip]
        print(f"Skip: excluded {before - len(races)} race(s) matching {args.skip}.")

    print("Loading dataset...")
    df = pd.read_csv(Path(__file__).resolve().parent.parent / "data" / "processed" / "combined_dataset.csv")
    df["LapSeconds"] = df["LapTime"].map(lambda v: lap_time_str_to_seconds(str(v)))
    df["Compound"] = df["Compound"].astype(str).str.upper()

    runner = BackendOptimizationRunner()

    print(f"Comparing {len(races)} race(s) against real results (re-solving both models each)...\n")

    append_mode = args.resume and out_path.exists()
    file_mode = "a" if append_mode else "w"
    rows_written = 0
    start_all = time.perf_counter()

    with out_path.open(file_mode, newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        if not append_mode:
            writer.writeheader()
        fh.flush()

        try:
            for idx, (year, race_name) in enumerate(races, start=1):
                year = int(year)
                t0 = time.perf_counter()
                baseline = get_real_baseline(df, year, race_name)
                if baseline is None:
                    print(f"[{idx}/{len(races)}] {year} {race_name}: no real finisher data, skipping")
                    continue

                payload = {"year": year, "race_name": race_name}
                try:
                    r1 = runner.run_scope1(payload)
                except Exception as exc:  # pragma: no cover - defensive
                    r1 = {"strategy": [], "solver_status": None, "message": f"EXCEPTION: {exc}"}
                try:
                    r2 = runner.run_scope2(payload)
                except Exception as exc:  # pragma: no cover - defensive
                    r2 = {"strategy": [], "solver_status": None, "message": f"EXCEPTION: {exc}"}

                for model_label, result, time_key in [
                    ("Model1_MILP", r1, "estimated_race_time_seconds"),
                    ("Model2_GoalProgramming", r2, "balanced_race_time_seconds"),
                ]:
                    if result.get("solver_status") != "Optimal" or not result.get("strategy"):
                        continue
                    pred_time = result.get(time_key)
                    if pred_time is None:
                        continue
                    delta = round(float(pred_time) - baseline["real_time_seconds"], 2)
                    outlier = 1 if abs(delta) > 500 else 0

                    writer.writerow({
                        "year": year,
                        "race": race_name,
                        "model": model_label,
                        "real_driver": baseline["real_driver"],
                        "real_time_seconds": baseline["real_time_seconds"],
                        "real_pit_stops": baseline["real_pit_stops"],
                        "real_strategy": baseline["real_strategy"],
                        "predicted_time_seconds": round(float(pred_time), 2),
                        "predicted_pit_stops": result.get("pit_stop_count") if "pit_stop_count" in result else len(result.get("pit_laps") or []),
                        "predicted_strategy": strategy_string(result),
                        "delta_seconds": delta,
                        "faster_than_real": delta < 0,
                        "outlier": outlier,
                    })
                    rows_written += 1
                fh.flush()

                elapsed = time.perf_counter() - t0
                print(f"[{idx}/{len(races)}] {year} {race_name} ({elapsed:.1f}s) -> "
                      f"real {baseline['real_driver']} {baseline['real_time_seconds']:.1f}s")
        except KeyboardInterrupt:
            print(f"\nInterrupted. {rows_written} row(s) written so far, safely flushed.")

    total_elapsed = time.perf_counter() - start_all
    print(f"\nWrote {rows_written} comparison rows to {out_path} in {total_elapsed:.1f}s")

    full = pd.read_csv(out_path)
    for model_label in ["Model1_MILP", "Model2_GoalProgramming"]:
        sub = full[full["model"] == model_label].dropna(subset=["delta_seconds"])
        if sub.empty:
            continue
        avg_delta = sub["delta_seconds"].mean()
        faster = sub["faster_than_real"].sum()
        print(f"{model_label}: avg delta vs real fastest = {avg_delta:+.2f}s "
              f"({faster}/{len(sub)} races beat the real fastest finisher)")


if __name__ == "__main__":
    main()
