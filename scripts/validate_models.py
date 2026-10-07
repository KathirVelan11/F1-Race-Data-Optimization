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
    parser.add_argument("--max-pit-stops", type=int, default=None, help="Override max_pit_stops input for every race.")
    parser.add_argument("--min-stint-length", type=int, default=None, help="Override min_stint_length input for every race.")
    parser.add_argument(
        "--out", type=str, default=str(Path(__file__).resolve().parent / "validation_report.csv"),
        help="Output CSV path.",
    )
    return parser.parse_args()


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
        "max_pit_stops": result.get("max_pit_stops"),
        "min_stint_length": result.get("min_stint_length"),
        "message": result.get("message", ""),
    }


def main() -> None:
    args = parse_args()
    runner = BackendOptimizationRunner()
    cases = build_race_list(runner, args)

    print(f"Validating {len(cases)} race(s) across {len({y for y, _ in cases})} season(s)...\n")

    rows = []
    failures = 0
    start_all = time.perf_counter()

    for idx, (year, race) in enumerate(cases, start=1):
        t0 = time.perf_counter()
        payload = {"year": year, "race_name": race}
        if args.max_pit_stops is not None:
            payload["max_pit_stops"] = args.max_pit_stops
        if args.min_stint_length is not None:
            payload["min_stint_length"] = args.min_stint_length

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
        rows.extend([row1, row2])

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

    total_elapsed = time.perf_counter() - start_all

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "year", "race", "model", "status", "ok", "issues", "total_laps", "laps_sum",
        "stint_count", "pit_stop_count", "race_time_seconds", "pit_loss_seconds",
        "max_pit_stops", "min_stint_length", "message",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    total_cases = len(cases)
    print(f"\n{'=' * 60}")
    print(f"Done in {total_elapsed:.1f}s. {total_cases - failures}/{total_cases} race(s) fully OK (both models).")
    print(f"Report written to: {out_path}")
    if failures:
        print(f"\n{failures} race(s) had at least one issue -- see the report or rerun with --races to isolate.")
        sys.exit(1)


if __name__ == "__main__":
    main()
