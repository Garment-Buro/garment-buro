"""Shared HTTP boundaries; each router retains its own authorization guard."""

from fastapi import HTTPException, Response

from app.modules.crm.directory_service import (
    InvalidReferenceCursor,
    ModelEditorSizeLimit,
    ReferenceDirectoryService,
)


async def read_reference_page(response: Response, operation):
    response.headers["Cache-Control"] = "no-store"
    try:
        return await operation
    except InvalidReferenceCursor as error:
        raise HTTPException(
            422, detail={"code": "invalid_cursor"}, headers={"Cache-Control": "no-store"}
        ) from error


async def read_model_detail(response: Response, session, model_id: int):
    response.headers["Cache-Control"] = "no-store"
    try:
        record = await ReferenceDirectoryService().model(session, model_id)
    except ModelEditorSizeLimit as error:
        raise HTTPException(
            409,
            {"code": "model_size_limit", "message": str(error)},
            headers={"Cache-Control": "no-store"},
        ) from error
    if record is None:
        raise HTTPException(404, "Модель не найдена", headers={"Cache-Control": "no-store"})
    return record
