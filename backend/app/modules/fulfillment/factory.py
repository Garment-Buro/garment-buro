from __future__ import annotations

from app.core.config import Settings
from app.modules.crm.handlers import CrmOrderProjectHandoffHandler
from app.modules.delivery.factory import build_cdek_request_codec
from app.modules.delivery.handlers import CdekShipmentHandoffHandler
from app.modules.fulfillment.contracts import FulfillmentHandler
from app.modules.fulfillment.handlers import OrderPaymentEmailHandler
from app.modules.fulfillment.worker import FulfillmentProcessor
from app.modules.notifications.factory import build_notification_outbox_service


def build_fulfillment_processor(settings: Settings) -> FulfillmentProcessor:
    handlers: list[FulfillmentHandler] = []
    if settings.fulfillment_email_enabled:
        handlers.append(
            OrderPaymentEmailHandler(
                build_notification_outbox_service(settings),
            )
        )
    if settings.fulfillment_cdek_enabled:
        handlers.append(
            CdekShipmentHandoffHandler(
                settings,
                build_cdek_request_codec(settings),
            )
        )
    if settings.fulfillment_crm_enabled:
        handlers.append(CrmOrderProjectHandoffHandler())
    if not handlers:
        raise RuntimeError(
            "FULFILLMENT_EMAIL_ENABLED, FULFILLMENT_CDEK_ENABLED, or "
            "FULFILLMENT_CRM_ENABLED is required"
        )
    return FulfillmentProcessor(settings, tuple(handlers))
