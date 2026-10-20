from urllib.parse import quote

from app.core.config import Settings
from app.modules.media.models import MediaObject
from app.modules.media.read_models import CatalogMediaView


def public_media_url(settings: Settings, media: MediaObject | CatalogMediaView) -> str:
    if media.object_key.startswith("uploads/"):
        return f"/{media.object_key}"
    public_base_url = (settings.minio_public_base_url or "").rstrip("/")
    if not public_base_url:
        raise RuntimeError("MINIO_PUBLIC_BASE_URL is required to map catalog media")
    return f"{public_base_url}/{media.bucket_name}/{quote(media.object_key, safe='/')}"
