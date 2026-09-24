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
    product_specs = (
        ("production-demo-hoodie-v1", "ТЕСТ · Худи для обучения", "navy"),
        ("production-demo-sweatshirt-v1", "ТЕСТ · Свитшот для обучения", "graphite"),
        ("production-demo-tshirt-v1", "ТЕСТ · Футболка для обучения", "white"),
    )
    products = []
    for slug, title, color in product_specs:
        product = await session.scalar(select(Product).where(Product.slug == slug))
        if product is None:
            product = Product(
                title=title,
                slug=slug,
                price=0,
                is_active=False,
                is_demo=True,
                sizes=["M"],
                colors=[color],
            )
            session.add(product)
            await session.flush()
        if product.is_active or not product.is_demo:
            raise ValueError("Demo catalog product must remain hidden and explicitly marked")
        products.append(product)
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
    for product in products:
        if product.garment_model_id is None:
            await service.link_catalog_product(
                session,
                garment_model_id=model.id,
                catalog_product_id=product.id,
                actor_user_id=actor,
            )
        elif product.garment_model_id != model.id:
            raise ValueError("Demo catalog product is linked to another garment model")
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
    return [product.id for product in products], size.id, revision.id
