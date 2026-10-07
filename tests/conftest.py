"""Pytest fixtures and configuration."""
from pathlib import Path
import pytest

from src.f1_optimizer.config.settings import settings


@pytest.fixture
def project_root() -> Path:
    """Fixture providing project root path."""
    return settings.project_root


@pytest.fixture
def processed_data_path() -> Path:
    """Fixture providing path to master combined dataset."""
    return settings.processed_data_path
