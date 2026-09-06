"""FloodGuard-AI FastAPI application."""

import logging
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.responses import Response

from apps.api.routers.drainage import router as drainage_router
from apps.api.routers.forcing import router as forcing_router
from apps.api.routers.harvester import router as harvester_router
from apps.api.routers.reconstruction import router as reconstruction_router
from apps.api.routers.registry import router as registry_router
from apps.api.routers.spatial import router as spatial_router
from apps.api.routers.terrain import router as terrain_router
from apps.api.routers.twin import router as twin_router
from apps.api.routers.urban_gis import router as urban_gis_router
from floodguard import __version__
from floodguard.common.auth import require_write_access
from floodguard.common.config import get_settings
from floodguard.common.logging import configure_logging
from floodguard.common.readiness import platform_readiness
from floodguard.common.release_evidence import lock_mismatches, source_fingerprint
from floodguard.contracts.time import UtcDateTime, utc_now
from floodguard.terrain.jobs import TerrainJobStore

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("floodguard.api")

app = FastAPI(
    title="FloodGuard-AI API",
    version=__version__,
    description="Urban flood digital twin platform API",
    dependencies=[Depends(require_write_access)],
)
app.state.terrain_jobs = TerrainJobStore()
app.include_router(registry_router)
app.include_router(harvester_router)
app.include_router(spatial_router)
app.include_router(reconstruction_router)
app.include_router(terrain_router)
app.include_router(urban_gis_router)
app.include_router(drainage_router)
app.include_router(twin_router)
app.include_router(forcing_router)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    timestamp: UtcDateTime


class ReadyResponse(BaseModel):
    status: Literal["ready"] = "ready"
    environment: str
    dependencies: dict[str, bool]
    timestamp: UtcDateTime


class VersionResponse(BaseModel):
    name: Literal["FloodGuard-AI"] = "FloodGuard-AI"
    version: str
    sequence: Literal[10] = 10
    source_fingerprint: str | None
    runtime_python: str
    dependency_lock_mismatches: list[str]


@app.middleware("http")
async def correlation_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    raw_id = request.headers.get("X-Correlation-ID")
    if raw_id:
        try:
            correlation_id = UUID(raw_id)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "X-Correlation-ID must be a valid UUID"},
            )
    else:
        correlation_id = uuid4()

    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = str(correlation_id)
    logger.info(
        "%s %s -> %s",
        request.method,
        request.url.path,
        response.status_code,
        extra={"correlation_id": correlation_id},
    )
    return response


@app.get("/health", response_model=HealthResponse, tags=["platform"])
def health() -> HealthResponse:
    return HealthResponse(timestamp=utc_now())


@app.get("/ready", response_model=ReadyResponse, tags=["platform"])
def ready() -> ReadyResponse | JSONResponse:
    checks = platform_readiness()
    if not checks or not all(checks.values()):
        return JSONResponse(
            status_code=503, content={"status": "not_ready", "dependencies": checks}
        )
    return ReadyResponse(environment=settings.environment, dependencies=checks, timestamp=utc_now())


@app.get("/version", response_model=VersionResponse, tags=["platform"])
def version() -> VersionResponse:
    root = Path(__file__).resolve().parents[2]
    try:
        fingerprint = source_fingerprint(root)
        mismatches = lock_mismatches(root / "requirements.lock")
    except (OSError, ValueError, ImportError):
        fingerprint = None
        mismatches = ["Release source/lockfile evidence unavailable"]
    return VersionResponse(
        version=__version__,
        source_fingerprint=fingerprint,
        runtime_python=sys.version.split()[0],
        dependency_lock_mismatches=mismatches,
    )
