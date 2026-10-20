from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def invalid_cursor_error() -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={"code": "invalid_cursor", "message": "The list changed; reload its first page"},
        headers={"Cache-Control": "no-store"},
    )


async def invalid_request_response(
    _request: Request, error: RequestValidationError
) -> JSONResponse:
    """Return field errors without copying customer documents or unsafe numeric input."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
                for item in error.errors()
            ]
        },
        headers={"Cache-Control": "no-store"},
    )
