"""Demo access is restricted independently of normal workstation permissions."""

from sqlalchemy import select

from app.modules.crm.file_models import CrmFileAttachment
from app.modules.crm.models import CrmOrderProject, CrmProductionUnit
from app.modules.orders.models import Order
from app.modules.production.models import ProductionDemoEmployee
from app.modules.production.security import ProductionDenied


async def is_demo_employee(session, user_id):
    return (
        await session.scalar(
            select(ProductionDemoEmployee.id).where(ProductionDemoEmployee.user_id == user_id)
        )
        is not None
    )


async def require_demo_project(session, user_id, project_id):
    if not await is_demo_employee(session, user_id):
        return
    allowed = await session.scalar(
        select(Order.id)
        .join(CrmOrderProject, CrmOrderProject.order_id == Order.id)
        .where(
            CrmOrderProject.id == project_id,
            CrmOrderProject.is_demo.is_(True),
            Order.is_demo.is_(True),
        )
    )
    if allowed is None:
        raise ProductionDenied("Демонстрационный код доступен только для тестовых заказов")


async def require_demo_resource(session, user_id, params):
    if not await is_demo_employee(session, user_id):
        return
    project_id = params.get("project_id")
    if "order_id" in params:
        project_id = await session.scalar(
            select(CrmOrderProject.id).where(CrmOrderProject.order_id == int(params["order_id"]))
        )
    unit_id = params.get("unit_id")
    if "attachment_id" in params:
        unit_id = await session.scalar(
            select(CrmFileAttachment.production_unit_id).where(
                CrmFileAttachment.id == int(params["attachment_id"])
            )
        )
        if unit_id is None:
            raise ProductionDenied("Учебному аккаунту недоступны общие производственные файлы")
    if unit_id is not None:
        project_id = await session.scalar(
            select(CrmProductionUnit.project_id).where(CrmProductionUnit.id == int(unit_id))
        )
    if params:
        await require_demo_project(session, user_id, int(project_id) if project_id else -1)
