"""FastAPI main application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import api_settings
from backend.app.api.routes import router

app = FastAPI(
    title=api_settings.api_title,
    version=api_settings.api_version,
    description="FastAPI backend for Formula 1 Race Strategy & Performance Optimization"
)

# CORS middleware for React frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=api_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=api_settings.api_prefix)
