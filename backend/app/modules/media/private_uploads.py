import asyncio

from app.integrations.minio import MinioStorage, StoredObject
from app.modules.media.errors import PrivateStorageUnavailableError


async def require_private_customer_storage(storage: MinioStorage) -> None:
    if (await storage.get_private_customer_bucket_policy() or "").strip():
        raise PrivateStorageUnavailableError("Customer storage must be private")


async def put_private_while_locked(
    storage: MinioStorage, *, object_key: str, data: bytes, content_type: str
) -> StoredObject:
    """Do not release a caller's SQL lock while an SDK thread can still write."""
    task = asyncio.create_task(
        storage.put_private_customer_object(
            object_key=object_key, data=data, content_type=content_type
        )
    )
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:  # noqa: BLE001 - preserve the original cancellation
                break
        if not task.cancelled():
            task.exception()
        raise
