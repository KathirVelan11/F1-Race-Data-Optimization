"""Validation script: run Model 1 (Scope 1 MILP) and Model 2 (Scope 2 Goal Programming)
across many races and years, and report pass/fail plus sanity-check metrics.

Usage:
    uv run python scripts/validate_models.py                 # all 148 races (slow, ~1-2hr)
    uv run python scripts/validate_models.py --quick          # ~3 races per year (fast)
    uv run python scripts/validate_models.py --years 2018 2024
    uv run python scripts/validate_models.py --races "Monaco Grand Prix" "Singapore Grand Prix"

Writes a CSV report to scripts/validation_report.csv and prints a summary to stdout.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.services.runner import BackendOptimizationRunner  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Model 1 / Model 2 across races and years.")
    parser.add_argument("--quick", action="store_true", help="Sample ~3 races per year instead of all races.")
    parser.add_argument("--years", type=int, nargs="*", default=None, help="Restrict to these years.")
    parser.add_argument("--races", type=str, nargs="*", default=None, help="Restrict to these race names.")
    parser.add_argument("--min-pit-stops", type=int, default=None, help="Override min_pit_stops input for every race.")
    parser.add_argument("--min-stint-length", type=int, default=None, help="Override min_stint_length input for every race.")
    parser.add_argument(
        "--out", type=str, default=str(Path(__file__).resolve().parent / "validation_report.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip races already present in --out (by year+race) and append new results instead of overwriting.",
    )
    return parser.parse_args()


def load_done_races(out_path: Path) -> set[tuple[int, str]]:
    """Read (year, race) pairs already present in an existing report, for --resume."""
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
        elif args.quick:
            step = max(1, len(races) // 3)
            races = races[::step][:3]
        for race in races:
            cases.append((year, race))

    if args.resume:
        done = load_done_races(Path(args.out))
        before = len(cases)
        cases = [c for c in cases if c not in done]
        print(f"Resume: {before - len(cases)} race(s) already in {args.out}, {len(cases)} remaining.")

    return cases


def check_result(label: str, result: dict, total_laps_expected: int | None) -> dict:
    """Run sanity checks on a solver result and return a row for the report."""
    strategy = result.get("strategy", [])
    status = result.get("solver_status")
    laps_sum = sum(stage["lap_count"] for stage in strategy)
    total_laps = result.get("total_laps")

    ok = bool(strategy) and status == "Optimal"
    issues = []

    if not strategy:
        issues.append("empty_strategy")
    if status != "Optimal":
        issues.append(f"status={status}")
    if total_laps and laps_sum != total_laps:
        issues.append(f"lap_mismatch({laps_sum}!={total_laps})")
        ok = False
    if total_laps_expected and total_laps and total_laps != total_laps_expected:
        issues.append(f"total_laps_disagrees_with_other_model({total_laps}!={total_laps_expected})")
        ok = False

    # Sanity: every stint should respect >=1 lap and a sane compound label.
    for stage in strategy:
        if stage.get("lap_count", 0) < 1:
            issues.append(f"zero_length_stint@{stage}")
            ok = False

    return {
        "model": label,
        "status": status,
        "ok": ok,
        "issues": ";".join(issues) if issues else "",
        "total_laps": total_laps,
        "laps_sum": laps_sum,
        "stint_count": len(strategy),
        "pit_stop_count": result.get("pit_stop_count") if "pit_stop_count" in result else len(result.get("pit_laps") or []),
        "race_time_seconds": result.get("estimated_race_time_seconds") or result.get("balanced_race_time_seconds"),
        "pit_loss_seconds": result.get("pit_loss_seconds"),
        "min_pit_stops": result.get("min_pit_stops"),
        "min_stint_length": result.get("min_stint_length"),
        "message": result.get("message", ""),
    }


FIELDNAMES = [
    "year", "race", "model", "status", "ok", "issues", "total_laps", "laps_sum",
    "stint_count", "pit_stop_count", "race_time_seconds", "pit_loss_seconds",
    "min_pit_stops", "min_stint_length", "message",
]


def main() -> None:
    args = parse_args()
    runner = BackendOptimizationRunner()
    cases = build_race_list(runner, args)

    print(f"Validating {len(cases)} race(s) across {len({y for y, _ in cases})} season(s)...")
    print("Safe to interrupt (Ctrl+C) at any point -- results are flushed to disk after every race.\n")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    failures = 0
    completed = 0
    start_all = time.perf_counter()

    append_mode = args.resume and out_path.exists()
    file_mode = "a" if append_mode else "w"
    with out_path.open(file_mode, newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        if not append_mode:
            writer.writeheader()
        fh.flush()

        try:
            for idx, (year, race) in enumerate(cases, start=1):
                t0 = time.perf_counter()
                payload = {"year": year, "race_name": race}
                if args.min_pit_stops is not None:
                    payload["min_pit_stops"] = args.min_pit_stops
                if args.min_stint_length is not None:
                    payload["min_stint_length"] = args.min_stint_length
                # max_sets_per_compound has no auto-default (blank = 0 sets, i.e. unusable)
                # -- bulk validation needs a generous per-race default so races aren't
                # trivially infeasible; 5 sets per real compound comfortably covers any
                # realistic stint count without constraining the solver's choices.
                race_compounds = runner._get_available_compounds(
                    runner.dataset_loader.get_race_dataframe(year, race)
                )
                payload["max_sets_per_compound"] = {compound: 5 for compound in race_compounds}

                try:
                    r1 = runner.run_scope1(payload)
                except Exception as exc:  # pragma: no cover - defensive
                    r1 = {"strategy": [], "solver_status": None, "message": f"EXCEPTION: {exc}"}

                try:
                    r2 = runner.run_scope2(payload)
                except Exception as exc:  # pragma: no cover - defensive
                    r2 = {"strategy": [], "solver_status": None, "message": f"EXCEPTION: {exc}"}

                row1 = check_result("Model1_MILP", r1, None)
                row2 = check_result("Model2_GoalProgramming", r2, r1.get("total_laps"))
                row1.update({"year": year, "race": race})
                row2.update({"year": year, "race": race})
                writer.writerow(row1)
                writer.writerow(row2)
                fh.flush()
                completed += 1

                elapsed = time.perf_counter() - t0
                status_mark = "OK" if (row1["ok"] and row2["ok"]) else "FAIL"
                if status_mark == "FAIL":
                    failures += 1
                print(
                    f"[{idx}/{len(cases)}] {year} {race} ({elapsed:.1f}s) -> {status_mark} "
                    f"| M1={row1['status']} laps={row1['laps_sum']}/{row1['total_laps']} "
                    f"| M2={row2['status']} laps={row2['laps_sum']}/{row2['total_laps']}"
                )
                if row1["issues"]:
                    print(f"    M1 issues: {row1['issues']}")
                if row2["issues"]:
                    print(f"    M2 issues: {row2['issues']}")
        except KeyboardInterrupt:
            print(f"\nInterrupted after {completed}/{len(cases)} race(s). Partial report saved.")

    total_elapsed = time.perf_counter() - start_all
    total_cases = len(cases)
    print(f"\n{'=' * 60}")
    print(f"Finished {completed}/{total_cases} race(s) in {total_elapsed:.1f}s. "
          f"{completed - failures}/{completed} fully OK (both models).")
    print(f"Report written to: {out_path}")
    if failures:
        print(f"\n{failures} race(s) had at least one issue -- see the report or rerun with --races to isolate.")
        sys.exit(1)


if __name__ == "__main__":
    main()
