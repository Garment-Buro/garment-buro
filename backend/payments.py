from __future__ import annotations

import uuid

from yookassa import Configuration, Payment
from yookassa.domain.common.confirmation_type import ConfirmationType
from yookassa.domain.models.currency import Currency

from app.core.config import Settings, get_settings
from app.core.exceptions import IntegrationNotConfiguredError


class YooKassaClient:
    def __init__(
        self,
        shop_id: str | None = None,
        api_key: str | None = None,
        webhook_url: str | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        runtime_settings = settings or get_settings()
        self.shop_id = shop_id or Settings.secret_value(runtime_settings.yookassa_shop_id)
        self.api_key = api_key or Settings.secret_value(runtime_settings.yookassa_api_key)
        self.webhook_url = webhook_url or runtime_settings.payment_webhook_url
        self._is_configured = False

    def _configure(self) -> None:
        if self._is_configured:
            return
        if not self.shop_id or not self.api_key:
            raise IntegrationNotConfiguredError("YooKassa is not configured")
        Configuration.configure(self.shop_id, self.api_key)
        self._is_configured = True

    def create_payment(
        self,
        amount: float,
        description: str,
        order_id: int,
        email: str,
        return_url: str,
        payment_method: str = "bank_card",
        *,
        idempotence_key: str | None = None,
    ) -> tuple[str, str]:
        """Create a payment and return its confirmation URL and provider ID."""
        self._configure()
        operation_key = idempotence_key or str(uuid.uuid4())

        payment_data = {
            "amount": {
                "value": f"{amount:.2f}",
                "currency": Currency.RUB,
            },
            "payment_method_data": {"type": payment_method},
            "confirmation": {
                "type": ConfirmationType.REDIRECT,
                "return_url": return_url,
            },
            "description": f"Оплата заказа #{order_id} - {description}",
            "metadata": {"order_id": str(order_id)},
            "capture": True,
            "receipt": {
                "customer": {"email": email},
                "items": [
                    {
                        "description": description[:64],
                        "quantity": "1.00",
                        "amount": {
                            "value": f"{amount:.2f}",
                            "currency": Currency.RUB,
                        },
                        "vat_code": 1,
                        "payment_mode": "full_payment",
                        "payment_subject": "commodity",
                    }
                ],
            },
        }

        payment = Payment.create(payment_data, operation_key)
        return payment.confirmation.confirmation_url, payment.id

    def get_payment_status(self, payment_id: str) -> str:
        self._configure()
        payment = Payment.find_one(payment_id)
        return payment.status
