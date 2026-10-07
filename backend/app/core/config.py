"""Backend application configuration."""
from typing import List
from pydantic import BaseModel, Field


class ApiSettings(BaseModel):
    """API server configuration."""
    api_title: str = "F1 Race Strategy & Performance Optimization API"
    api_version: str = "0.1.0"
    api_prefix: str = "/api"
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])


api_settings = ApiSettings()
