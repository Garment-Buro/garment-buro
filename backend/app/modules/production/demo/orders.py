from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy import select

from app.modules.crm.models import CrmOrderProject, CrmProductionUnit, CrmProjectEvent
from app.modules.orders.models import Order, OrderItem, OrderStatusHistory


async def ensure_order(session, station, label, product_id, actor):
    fingerprint = sha256(f"production-demo-v1:{station}".encode()).hexdigest()
    order = await session.scalar(
        select(Order).where(Order.request_fingerprint_sha256 == fingerprint)
    )
    if order:
        if not order.is_demo:
            raise ValueError("Existing order is not a demo")
        project = await session.scalar(
            select(CrmOrderProject).where(CrmOrderProject.order_id == order.id)
        )
        unit = await session.scalar(
            select(CrmProductionUnit).where(CrmProductionUnit.project_id == project.id)
        )
        return order.id, project.id, unit.id, False
    now = datetime.now(timezone.utc)
    order = Order(
        is_demo=True,
        first_name="ТЕСТ",
        last_name=label,
        delivery_method="demo",
        delivery_city="Учебный цех",
        delivery_address="Не отправлять",
        phone="DEMO-NOT-A-PHONE",
        items_subtotal=0,
        delivery_price=0,
        total_price=0,
        status="processing",
        payment_status="pending",
        payment_method="production_demo",
        request_fingerprint_sha256=fingerprint,
        items=[
            OrderItem(
                client_item_id=f"demo-{station}",
                product_id_snapshot=product_id,
                title_snapshot="ТЕСТ · Худи, учебный образец",
                unit_price=0,
                quantity=1,
                line_total=0,
                size_snapshot="M",
                color_snapshot="navy",
                sort_order=0,
                image_url_snapshot="/nikitamoiseev/hoodie-front.png",
                customization_snapshot={
                    "modelImages": {
                        "front": "/nikitamoiseev/hoodie-front.png",
                        "back": "/nikitamoiseev/hoodie-back-model.png",
                    },
                    "comment": "Учебные изображения. Не использовать как производственные лекала.",
                },
            )
        ],
    )
    session.add(order)
    await session.flush()
    session.add(
        OrderStatusHistory(
            order_id=order.id,
            version=order.version,
            to_status="processing",
            reason_code="production.demo_created",
            actor_user_id=actor,
        )
    )
    project = CrmOrderProject(
        order_id=order.id,
        is_demo=True,
        source_fulfillment_job_id=None,
        source_payment_attempt_id=None,
        order_version_snapshot=order.version,
        items_count=1,
        units_count=1,
        total_price_snapshot=0,
        currency="RUB",
        payment_succeeded_at_snapshot=None,
    )
    session.add(project)
    await session.flush()
    unit = CrmProductionUnit(
        project_id=project.id,
        order_item_id=order.items[0].id,
        product_id_snapshot=product_id,
        unit_number=1,
    )
    session.add(unit)
    session.add(
        CrmProjectEvent(
            project_id=project.id,
            event_key=f"demo:{fingerprint}",
            version=1,
            to_status="queued",
            reason_code="production_demo_created",
            actor_user_id=actor,
            occurred_at=now,
        )
    )
    await session.commit()
    return order.id, project.id, unit.id, True
