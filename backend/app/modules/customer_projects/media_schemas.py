from pydantic import BaseModel


class ProjectImage(BaseModel):
    id: int
    content_type: str
    size_bytes: int


class ProjectImageAccess(ProjectImage):
    url: str
    expires_in: int


class ResolvedProjectImage(ProjectImage):
    url: str
    expires_in: int | None


class ProjectImages(BaseModel):
    version: int
    items: list[ResolvedProjectImage]
