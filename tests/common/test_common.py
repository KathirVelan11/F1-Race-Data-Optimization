"""Tests for common module components."""
import pytest


def test_time_conversion_utils():
    """Verify lap time parsing utility works correctly."""
    from src.f1_optimizer.common.utils.time_utils import lap_time_str_to_seconds, seconds_to_lap_time_str

    assert lap_time_str_to_seconds("1:28.176") == pytest.approx(88.176)
    assert lap_time_str_to_seconds("90.500") == pytest.approx(90.5)
    assert seconds_to_lap_time_str(88.176) == "1:28.176"


def test_dataset_loader_reads_master_csv():
    """Verify DatasetLoader successfully reads without schema corruption."""
    from src.f1_optimizer.common.data.dataset_loader import DatasetLoader

    loader = DatasetLoader()
    seasons = loader.get_available_seasons()
    assert seasons
    assert 2018 in seasons
    summary = loader.get_race_summary(2024, "Australian Grand Prix")
    assert summary["total_laps"] >= 50
    assert len(summary["drivers"]) > 0


def test_tyre_degradation_fitting():
    """Verify tyre degradation model fits a non-negative slope from real race data."""
    from src.f1_optimizer.common.data.dataset_loader import DatasetLoader
    from src.f1_optimizer.common.tyre.degradation_model import TyreDegradationModel

    race_df = DatasetLoader().get_race_dataframe(2024, "Australian Grand Prix")
    compound = race_df["Compound"].dropna().astype(str).str.upper().mode()[0]

    model = TyreDegradationModel()
    base_lap_time, degradation_rate = model.fit_compound_degradation(race_df, compound)

    assert base_lap_time > 0
    assert degradation_rate >= 0


def test_tyre_degradation_fitting_raises_without_data():
    """Verify the model refuses to fabricate a result when there's no real data to fit."""
    import pandas as pd
    import pytest as _pytest
    from src.f1_optimizer.common.tyre.degradation_model import TyreDegradationModel

    with _pytest.raises(ValueError):
        TyreDegradationModel().fit_compound_degradation(pd.DataFrame(), "SOFT")
