from sqlalchemy import select

from app.modules.catalog.models import Product
from app.modules.crm.reference_models import (
    CrmGarmentModel,
    CrmGarmentSize,
    CrmTechCard,
    CrmTechCardRevision,
)
from app.modules.crm.reference_schemas import (
    CrmGarmentModelWrite,
    CrmGarmentSizeWrite,
    CrmTechCardCheckpointWrite,
    CrmTechCardCreate,
    CrmTechCardRevisionWrite,
)
from app.modules.crm.reference_service import CrmReferenceService


async def ensure_references(session, actor):
    product = await session.scalar(
        select(Product).where(Product.slug == "production-demo-hoodie-v1")
    )
    if product is None:
        product = Product(
            title="ТЕСТ · Худи для обучения",
            slug="production-demo-hoodie-v1",
            price=0,
            is_active=False,
            sizes=["M"],
            colors=["navy"],
        )
        session.add(product)
        await session.flush()
    if product.is_active:
        raise ValueError("Demo catalog product must remain hidden")
    service = CrmReferenceService()
    model = await session.scalar(
        select(CrmGarmentModel).where(CrmGarmentModel.code == "DEMO_HOODIE_V1")
    )
    if model is None:
        model = await service.create_garment_model(
            session,
            actor_user_id=actor,
            payload=CrmGarmentModelWrite(
                code="DEMO_HOODIE_V1",
                name="ТЕСТ · Учебное худи",
                sizes=[CrmGarmentSizeWrite(code="M")],
            ),
        )
        await service.link_catalog_product(
            session, garment_model_id=model.id, catalog_product_id=product.id, actor_user_id=actor
        )
        card = await service.create_tech_card(
            session,
            garment_model_id=model.id,
            actor_user_id=actor,
            payload=CrmTechCardCreate(
                code="DEMO_CARD_V1",
                revision=CrmTechCardRevisionWrite(
                    name="Учебная карта, не для реального производства",
                    checkpoints=[
                        CrmTechCardCheckpointWrite(
                            position=1,
                            stage_code="sewing",
                            name="Учебная проверка швов",
                            standard_minutes=10,
                            labor_cost=0,
                        )
                    ],
                ),
            ),
        )
        await service.publish_tech_card_revision(
            session, tech_card_id=card.id, revision_number=1, actor_user_id=actor
        )
    size = await session.scalar(
        select(CrmGarmentSize).where(CrmGarmentSize.garment_model_id == model.id)
    )
    revision = await session.scalar(
        select(CrmTechCardRevision)
        .join(CrmTechCard)
        .where(CrmTechCard.garment_model_id == model.id, CrmTechCardRevision.status == "published")
    )
    if size is None or revision is None:
        raise ValueError("Demo reference is incomplete; do not overwrite operator changes")
    await session.commit()
    return product.id, size.id, revision.id
