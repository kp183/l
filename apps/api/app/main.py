"""AgentLens API — application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.exceptions import AgentLensError
from app.middleware.logging import RequestIDMiddleware, setup_logging

setup_logging()
from app.routers.api_keys import router as api_keys_router
from app.routers.health import router as health_router
from app.routers.ingest import router as ingest_router
from app.routers.orgs import router as orgs_router
from app.routers.traces import router as traces_router
from app.routers.ws import router as ws_router

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="AgentLens API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(RequestIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ────────────────────────────────────────────────────────


@app.exception_handler(AgentLensError)
async def agentlens_error_handler(request: Request, exc: AgentLensError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error("AgentLensError: %s", exc.message, extra={"request_id": request_id})
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("Unhandled exception", extra={"request_id": request_id})
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "request_id": request_id,
            }
        },
    )


# ── Startup ───────────────────────────────────────────────────────────────────


@app.on_event("startup")
async def run_migrations() -> None:
    """Run Alembic migrations on startup in development mode."""
    if settings.environment != "development":
        return

    import asyncio
    from alembic import command
    from alembic.config import Config

    logger.info("Running Alembic migrations (environment=development)...")
    try:
        alembic_cfg = Config("alembic.ini")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, command.upgrade, alembic_cfg, "head")
        logger.info("Alembic migrations complete.")
    except Exception as exc:
        logger.error("Migration failed: %s", exc)
        raise


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health_router)
app.include_router(orgs_router)
app.include_router(api_keys_router)
app.include_router(ingest_router)
app.include_router(traces_router)
app.include_router(ws_router)
