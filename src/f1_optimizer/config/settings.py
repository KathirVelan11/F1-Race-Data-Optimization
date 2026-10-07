"""Configuration and settings for F1 Strategy Optimizer."""
from pathlib import Path
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Application settings and global parameters."""

    # Project paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3])
    data_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3] / "data")
    processed_data_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[3] / "data" / "processed" / "combined_dataset.csv"
    )

    # Default Optimization Parameters (from Project PPT)
    default_pit_stop_loss_seconds: float = 13.0  # As defined in Slide 10 MILP parameters (P ≈ 13s)
    default_intro_pit_loss_seconds: float = 20.0  # Referenced in introductory background
    max_pit_stops: int = 2                       # Slide 11 constraint (b)
    min_stint_length: int = 5                    # Slide 11 constraint (d)

    # Default Durability Limits (laps) - L_c^max
    default_max_stint_soft: int = 25
    default_max_stint_medium: int = 40
    default_max_stint_hard: int = 55

    # Scope 2 Default Weights
    default_weight_time: float = 0.50
    default_weight_pit_stops: float = 0.25
    default_weight_degradation: float = 0.25


settings = Settings()
