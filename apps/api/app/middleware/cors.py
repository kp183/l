"""CORS middleware configuration.

Uses an explicit origin allowlist from Settings.
Wildcard '*' is never permitted.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings


def add_cors_middleware(app: FastAPI) -> None:
    """Attach CORSMiddleware to *app* using the configured origin allowlist."""
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
