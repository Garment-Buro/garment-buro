from fastapi import APIRouter, HTTPException

router = APIRouter(include_in_schema=False)


@router.api_route(
    "/admin",
    methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
@router.api_route(
    "/admin/{path:path}",
    methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def retired_legacy_admin(path: str = "") -> None:
    del path
    raise HTTPException(status_code=404, detail="Not found")
