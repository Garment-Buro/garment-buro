from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage

router = APIRouter(tags=["system"])


class LivenessResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    storage: str


@router.get("/health/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
async def readiness(request: Request) -> ReadinessResponse | JSONResponse:
    database = request.app.state.database
    storage = request.app.state.storage
    if not isinstance(database, DatabaseManager) or not database.enabled:
        database_status = "disabled"
    elif await database.ping():
        database_status = database.backend_name
    else:
        return JSONResponse(
            status_code=503,
            content=ReadinessResponse(
                status="not_ready",
                database=database.backend_name,
                storage=(storage.backend_name if isinstance(storage, MinioStorage) else "unknown"),
            ).model_dump(),
        )

    if not isinstance(storage, MinioStorage) or not storage.enabled:
        storage_status = "disabled"
    elif await storage.ping():
        storage_status = storage.backend_name
    else:
        return JSONResponse(
            status_code=503,
            content=ReadinessResponse(
                status="not_ready",
                database=database_status,
                storage=storage.backend_name,
            ).model_dump(),
        )

    background_failed = any(
        task.done() for task in getattr(request.app.state, "runtime_tasks", {}).values()
    )
    result = ReadinessResponse(
        status="not_ready" if background_failed else "ready",
        database=database_status,
        storage=storage_status,
    )
    if background_failed:
        return JSONResponse(status_code=503, content=result.model_dump())
    return result
