from datetime import datetime

from sqlalchemy import case, delete, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.carts.models import Cart
from app.modules.design_assets.models import CartDesignAsset, DesignAsset, OrderDesignAsset
from app.modules.design_assets.security import (
    DesignAssetUnavailableError,
    digest_design_asset_token,
)
from app.modules.identity.security import ensure_utc
from app.modules.media.models import MediaObject, MediaStatus


def require_available(
    asset: DesignAsset, media: MediaObject, *, bucket_name: str, now: datetime, held: bool
) -> None:
    if (
        media.status != MediaStatus.READY.value
        or media.is_public
        or media.provider != "minio"
        or media.bucket_name != bucket_name
        or media.content_type not in {"image/jpeg", "image/png", "image/webp"}
        or (
            asset.expires_at is not None
            and ensure_utc(asset.expires_at) <= ensure_utc(now)
            and not held
        )
    ):
        raise DesignAssetUnavailableError("Design image is unavailable")


def retained(now: datetime):
    return or_(
        exists(
            select(OrderDesignAsset.order_id).where(
                OrderDesignAsset.design_asset_id == DesignAsset.id
            )
        ),
        exists(
            select(CartDesignAsset.cart_id)
            .join(Cart, Cart.id == CartDesignAsset.cart_id)
            .where(CartDesignAsset.design_asset_id == DesignAsset.id, Cart.expires_at > now)
        ),
    )


class DesignAssetRepository:
    async def available_media(
        self, session: AsyncSession, *, token: str, bucket_name: str, now: datetime
    ) -> MediaObject:
        row = (
            await session.execute(
                select(DesignAsset, MediaObject, retained(now))
                .join(MediaObject, MediaObject.id == DesignAsset.media_object_id)
                .where(DesignAsset.access_digest_sha256 == digest_design_asset_token(token))
                .execution_options(populate_existing=True)
            )
        ).one_or_none()
        if row is None:
            raise DesignAssetUnavailableError("Design image is unavailable")
        asset, media, held = row
        require_available(asset, media, bucket_name=bucket_name, now=now, held=held)
        return media

    async def lock_owned_media(
        self, session: AsyncSession, *, user_id: int, media_ids: list[int], bucket_name: str
    ) -> list[MediaObject]:
        rows = list(
            await session.scalars(
                select(MediaObject)
                .where(
                    MediaObject.id.in_(set(media_ids)),
                    MediaObject.uploaded_by_user_id == user_id,
                    MediaObject.provider == "minio",
                    MediaObject.bucket_name == bucket_name,
                    MediaObject.object_key.startswith(f"projects/{user_id}/"),
                    MediaObject.is_public.is_(False),
                    MediaObject.status == MediaStatus.READY.value,
                    MediaObject.content_type.in_(("image/jpeg", "image/png", "image/webp")),
                )
                .order_by(MediaObject.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        if len(rows) != len(set(media_ids)):
            raise DesignAssetUnavailableError("Design image is unavailable")
        return rows

    async def lock_available(
        self, session: AsyncSession, *, tokens: list[str], bucket_name: str, now: datetime
    ) -> list[DesignAsset]:
        digests = {digest_design_asset_token(token) for token in tokens}
        # 100 lines, each with 100 placements, 2 model images and 1 thumbnail.
        if len(digests) > 10_300:
            raise DesignAssetUnavailableError("Too many design images")
        if not digests:
            return []
        assets = list(
            await session.scalars(
                select(DesignAsset)
                .where(DesignAsset.access_digest_sha256.in_(digests))
                .order_by(DesignAsset.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        if len(assets) != len(digests):
            raise DesignAssetUnavailableError("Design image is unavailable")
        # Lock capabilities first, then objects in their own stable order. Two
        # capabilities may reference the same media in different asset orders.
        # This fresh statement also sees references committed before asset locks.
        rows = (
            await session.execute(
                select(DesignAsset, MediaObject, retained(now))
                .join(MediaObject, MediaObject.id == DesignAsset.media_object_id)
                .where(DesignAsset.id.in_([asset.id for asset in assets]))
                .order_by(MediaObject.id, DesignAsset.id)
                .with_for_update(of=MediaObject)
                .execution_options(populate_existing=True)
            )
        ).all()
        for asset, media, held in rows:
            require_available(asset, media, bucket_name=bucket_name, now=now, held=held)
        return assets

    async def replace_cart_links(
        self, session: AsyncSession, *, cart_id: int, assets: list[DesignAsset]
    ) -> None:
        """Caller owns the cart lock and obtains assets through lock_available first."""
        await session.execute(delete(CartDesignAsset).where(CartDesignAsset.cart_id == cart_id))
        session.add_all(
            CartDesignAsset(cart_id=cart_id, design_asset_id=asset_id)
            for asset_id in {asset.id for asset in assets}
        )
        if assets:
            expiry = select(Cart.expires_at).where(Cart.id == cart_id).scalar_subquery()
            await session.execute(
                update(DesignAsset)
                .where(
                    DesignAsset.id.in_([asset.id for asset in assets]),
                    DesignAsset.expires_at.is_not(None),
                )
                .values(
                    expires_at=case(
                        (DesignAsset.expires_at < expiry, expiry), else_=DesignAsset.expires_at
                    )
                )
            )
        await session.flush()

    async def retain_order(
        self, session: AsyncSession, *, order_id: int, assets: list[DesignAsset]
    ) -> None:
        """Caller holds the order transaction and locks assets before accepting the order."""
        existing = set(
            await session.scalars(
                select(OrderDesignAsset.design_asset_id).where(
                    OrderDesignAsset.order_id == order_id
                )
            )
        )
        session.add_all(
            OrderDesignAsset(order_id=order_id, design_asset_id=asset_id)
            for asset_id in {asset.id for asset in assets} - existing
        )
        if assets:
            await session.execute(
                update(DesignAsset)
                .where(DesignAsset.id.in_([asset.id for asset in assets]))
                .values(expires_at=None)
            )
        await session.flush()

    async def prune_expired(
        self, session: AsyncSession, *, now: datetime, limit: int = 100, dry_run: bool = False
    ) -> list[int]:
        """Detach only expired unretained capabilities; object deletion is a later durable step."""
        if not 1 <= limit <= 1000:
            raise ValueError("Design cleanup batch size must be between 1 and 1000")
        candidates = list(
            await session.scalars(
                select(DesignAsset)
                .where(DesignAsset.expires_at <= now, ~retained(now))
                .order_by(DesignAsset.expires_at, DesignAsset.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )
        )
        if not candidates:
            return []
        ids = [asset.id for asset in candidates]
        # An attachment waiting ahead of these locks may have committed already.
        held = set(
            await session.scalars(
                select(DesignAsset.id).where(DesignAsset.id.in_(ids), retained(now))
            )
        )
        removable = [
            asset for asset in candidates if asset.id not in held and asset.expires_at is not None
        ]
        ids = [asset.id for asset in removable]
        media_ids = list({asset.media_object_id for asset in removable})
        if ids and not dry_run:
            # Different capabilities in concurrent batches can share objects.
            # Use the same global object order as checkout/cart attachments.
            await session.execute(
                select(MediaObject.id)
                .where(MediaObject.id.in_(media_ids))
                .order_by(MediaObject.id)
                .with_for_update()
            )
            await session.execute(
                delete(CartDesignAsset).where(CartDesignAsset.design_asset_id.in_(ids))
            )
            await session.execute(delete(DesignAsset).where(DesignAsset.id.in_(ids)))
            await session.execute(
                update(MediaObject).where(MediaObject.id.in_(media_ids)).values(updated_at=now)
            )
        return media_ids
