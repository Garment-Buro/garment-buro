import asyncio

import pytest

from app.modules.identity.models import User
from app.modules.identity.security import OtpSecurity
from app.modules.orders.models import Order
from app.modules.orders.service import TargetOrderReadService
from app.modules.orders.workflow import customer_stage_for_state
from app.modules.orders.workflow_models import OrderWorkflow
from tests.unit.test_order_workflow import setup


@pytest.mark.parametrize(
    ("state", "stage", "label"),
    [
        ("awaiting_payment", "awaiting_payment", "Ожидает оплаты"),
        ("moderation", "moderation", "Модерация"),
        ("capture_pending", "moderation", "Модерация"),
        ("cancel_pending", "moderation", "Модерация"),
        ("production", "production", "Производство"),
        ("shipped", "shipped", "Передано в СДЭК"),
        ("completed", "completed", "Выполнено"),
        ("cancelled", "cancelled", "Отменён"),
        ("attention", "attention", "Требуется проверка менеджера"),
        (None, None, None),
        ("unrecognized", None, None),
    ],
)
def test_customer_stage_covers_workflow_without_guessing_unknown_states(state, stage, label):
    assert customer_stage_for_state(state) == (stage, label)


def test_history_and_full_document_agree_on_persisted_workflow_stages(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (database, _, _, _):
            reads = TargetOrderReadService(OtpSecurity("p" * 32))
            async with database.session() as session:
                owner = await session.get(User, 1)
                order = await session.get(Order, 1)
                flow = await session.get(OrderWorkflow, 1)
                order.user_id = owner.id
                # Projection fixture: business transition rules are covered separately.
                for state, stage, label in [
                    ("awaiting_payment", "awaiting_payment", "Ожидает оплаты"),
                    ("moderation", "moderation", "Модерация"),
                    ("capture_pending", "moderation", "Модерация"),
                    ("cancel_pending", "moderation", "Модерация"),
                    ("production", "production", "Производство"),
                    ("shipped", "shipped", "Передано в СДЭК"),
                    ("completed", "completed", "Выполнено"),
                    ("cancelled", "cancelled", "Отменён"),
                    ("attention", "attention", "Требуется проверка менеджера"),
                ]:
                    flow.state = state
                    await session.flush()
                    page = await reads.list_owned_orders(session, user=owner)
                    document = await reads.get_owned_order(session, user=owner, order_id=order.id)
                    for item in [page.items[0], document]:
                        assert (item.customer_stage, item.customer_stage_label) == (stage, label)
                        assert item.payment_status == "pending"

    asyncio.run(scenario())
