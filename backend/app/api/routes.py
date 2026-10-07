"""FastAPI route declarations for the F1 strategy optimization project."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.app.services.runner import BackendOptimizationRunner

router = APIRouter()
runner = BackendOptimizationRunner()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "app": "F1 Race Strategy & Performance Optimizer"}


@router.get("/dashboard")
async def get_dashboard_summary():
    """Return the application dashboard summary."""
    return runner.get_dashboard_summary()


@router.get("/dataset/overview")
async def get_dataset_overview():
    """Return a detailed breakdown of the combined dataset."""
    return runner.get_dataset_overview()


@router.get("/races/seasons")
async def get_available_seasons():
    """Return all seasons available in the dataset."""
    return {"seasons": runner.get_dashboard_summary()["years"]}


@router.get("/races")
async def get_races_for_year(year: int = Query(..., ge=2018, le=2025)):
    """Return race names for a given season."""
    return {"year": year, "races": runner.get_races_for_season(year)}


@router.get("/races/{year}/{race_name}/drivers")
async def get_drivers_for_race(year: int, race_name: str):
    """Return available drivers for a selected race."""
    return {"year": year, "race_name": race_name, "drivers": runner.get_drivers_for_race(year, race_name)}


@router.get("/races/{year}/{race_name}/summary")
async def get_race_summary(year: int, race_name: str, driver_code: Optional[str] = None):
    """Return a compact summary of a race for the UI."""
    summary = runner.get_race_summary(year, race_name, driver_code)
    if summary.get("total_laps", 0) == 0:
        raise HTTPException(status_code=404, detail="Race data not found")
    return summary


@router.get("/races/{year}/{race_name}/strategy-preview")
async def get_strategy_preview(year: int, race_name: str, driver_code: Optional[str] = None):
    """Return a simple strategy preview for the frontend."""
    preview = runner.build_strategy_preview(year, race_name, driver_code)
    if not preview.get("strategy"):
        raise HTTPException(status_code=404, detail="No strategy preview could be constructed for this selection")
    return preview


@router.post("/scope1/optimize")
async def optimize_scope1(payload: dict):
    """Prototype Scope 1 optimization endpoint."""
    return runner.run_scope1(payload)


@router.post("/scope2/optimize")
async def optimize_scope2(payload: dict):
    """Prototype Scope 2 optimization endpoint."""
    return runner.run_scope2(payload)


@router.post("/compare")
async def compare_strategies(payload: dict):
    """Comparison endpoint for the two optimization approaches."""
    return runner.run_comparison(payload)
