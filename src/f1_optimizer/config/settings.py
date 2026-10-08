"""Configuration and settings for F1 Strategy Optimizer."""
from pathlib import Path
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Application settings: file paths only.

    Optimization parameters (pit loss, max pit stops, min stint length, durability,
    goal weights) are intentionally NOT here -- they vary per race and must be derived
    from real data by BackendOptimizationRunner, not read from a fixed global constant.
    """

    # Project paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3])
    data_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3] / "data")
    processed_data_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[3] / "data" / "processed" / "combined_dataset.csv"
    )


settings = Settings()
