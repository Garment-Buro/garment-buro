from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from jinja2 import Environment, StrictUndefined, select_autoescape

from app.modules.notifications.models import NotificationTemplate

AUTH_OTP_TEMPLATE = """
<!doctype html>
<html lang="ru">
<body style="font-family: Inter, Arial, sans-serif; background:#f7f7f7; padding:40px">
  <div style="max-width:500px;margin:0 auto;background:#fff;padding:40px;border-radius:20px">
    <h1 style="font-size:24px;text-align:center">Код подтверждения</h1>
    <p style="font-size:16px;color:#666;text-align:center">
      Используйте этот код для {{ action_label }} на garment-buro.
    </p>
    <div style="background:#f2f2f2;padding:20px;text-align:center;border-radius:12px">
      <span style="font-size:32px;font-weight:700;letter-spacing:5px">{{ code }}</span>
    </div>
    <p style="font-size:12px;color:#999;text-align:center;margin-top:30px">
      Код действует {{ expires_minutes }} минут. Если вы его не запрашивали,
      просто проигнорируйте письмо.
    </p>
  </div>
</body>
</html>
"""

ORDER_PAYMENT_CONFIRMED_TEMPLATE = """
<!doctype html>
<html lang="ru">
<body style="font-family: Inter, Arial, sans-serif; background:#f7f7f7; padding:24px">
  <div style="max-width:600px;margin:0 auto;background:#fff;padding:32px;border-radius:20px">
    <h1 style="font-size:24px;text-align:center">Заказ #{{ order_id }} оплачен</h1>
    <p style="font-size:16px;color:#444;text-align:center">
      {% if first_name %}{{ first_name }}, спасибо за заказ!{% else %}Спасибо за заказ!{% endif %}
      Мы получили оплату и начали обработку.
    </p>
    <table style="width:100%;border-collapse:collapse;margin-top:24px">
      {% for item in items %}
      <tr style="border-bottom:1px solid #eee">
        <td style="padding:12px 0">
          <strong>{{ item.title }}</strong><br>
          <span style="font-size:12px;color:#666">
            {% if item.size %}Размер: {{ item.size }}{% endif %}
            {% if item.size and item.color %}, {% endif %}
            {% if item.color %}цвет: {{ item.color }}{% endif %}
          </span>
        </td>
        <td style="padding:12px 0;text-align:right;white-space:nowrap">
          {{ item.quantity }} × {{ item.unit_price }} ₽
        </td>
      </tr>
      {% endfor %}
    </table>
    <div style="margin-top:20px;color:#666;text-align:right">
      Товары: {{ items_subtotal }} ₽<br>
      Доставка: {{ delivery_price }} ₽
    </div>
    <div style="margin-top:8px;font-size:20px;font-weight:700;text-align:right">
      Итого: {{ total_price }} ₽
    </div>
    <p style="font-size:12px;color:#999;text-align:center;margin-top:30px">
      Статус и детали заказа доступны на сайте garment-buro.
    </p>
  </div>
</body>
</html>
"""


class InvalidNotificationPayloadError(RuntimeError):
    pass


class UnsupportedNotificationTemplateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    recipient: str
    subject: str
    html: str


class NotificationRenderer:
    def __init__(self) -> None:
        self.environment = Environment(
            autoescape=select_autoescape(default_for_string=True),
            undefined=StrictUndefined,
        )
        self.auth_otp_template = self.environment.from_string(AUTH_OTP_TEMPLATE)
        self.order_payment_confirmed_template = self.environment.from_string(
            ORDER_PAYMENT_CONFIRMED_TEMPLATE
        )

    def render_email(
        self,
        template: str,
        payload: dict[str, object],
    ) -> RenderedEmail:
        if template == NotificationTemplate.AUTH_OTP.value:
            return self._render_auth_otp(payload)
        if template == NotificationTemplate.ORDER_PAYMENT_CONFIRMED.value:
            return self._render_order_payment_confirmed(payload)
        raise UnsupportedNotificationTemplateError(f"Unsupported notification template: {template}")

    def _render_auth_otp(self, payload: dict[str, object]) -> RenderedEmail:
        recipient = payload.get("recipient")
        code = payload.get("code")
        purpose = payload.get("purpose")
        expires_minutes = payload.get("expires_minutes")
        if (
            not isinstance(recipient, str)
            or "@" not in recipient
            or not isinstance(code, str)
            or not 4 <= len(code) <= 8
            or not code.isdigit()
            or purpose not in {"login", "email_change"}
            or not isinstance(expires_minutes, int)
            or not 1 <= expires_minutes <= 60
        ):
            raise InvalidNotificationPayloadError("Invalid auth OTP notification payload")
        action_label = "входа" if purpose == "login" else "изменения email"
        return RenderedEmail(
            recipient=recipient,
            subject="Код подтверждения для garment-buro",
            html=self.auth_otp_template.render(
                action_label=action_label,
                code=code,
                expires_minutes=expires_minutes,
            ),
        )

    def _render_order_payment_confirmed(
        self,
        payload: dict[str, object],
    ) -> RenderedEmail:
        recipient = payload.get("recipient")
        order_id = payload.get("order_id")
        first_name = payload.get("first_name")
        items = payload.get("items")
        currency = payload.get("currency")
        if (
            not isinstance(recipient, str)
            or not 3 <= len(recipient) <= 320
            or "@" not in recipient
            or any(character.isspace() for character in recipient)
            or type(order_id) is not int
            or order_id <= 0
            or (first_name is not None and not self._bounded_text(first_name, maximum=255))
            or not isinstance(items, list)
            or not 1 <= len(items) <= 100
            or currency != "RUB"
        ):
            raise InvalidNotificationPayloadError("Invalid order payment notification payload")

        rendered_items: list[dict[str, object]] = []
        calculated_subtotal = Decimal("0.00")
        for item in items:
            if not isinstance(item, dict):
                raise InvalidNotificationPayloadError("Invalid order payment notification item")
            title = item.get("title")
            size = item.get("size")
            color = item.get("color")
            quantity = item.get("quantity")
            if (
                not self._bounded_text(title, maximum=255)
                or not self._optional_bounded_text(size, maximum=32)
                or not self._optional_bounded_text(color, maximum=64)
                or type(quantity) is not int
                or not 1 <= quantity <= 1_000
            ):
                raise InvalidNotificationPayloadError("Invalid order payment notification item")
            unit_price = self._money(item.get("unit_price"))
            line_total = self._money(item.get("line_total"))
            if unit_price <= 0 or line_total != unit_price * quantity:
                raise InvalidNotificationPayloadError(
                    "Invalid order payment notification item totals"
                )
            calculated_subtotal += line_total
            rendered_items.append(
                {
                    "title": title,
                    "size": size,
                    "color": color,
                    "quantity": quantity,
                    "unit_price": f"{unit_price:.2f}",
                }
            )

        items_subtotal = self._money(payload.get("items_subtotal"))
        delivery_price = self._money(payload.get("delivery_price"))
        total_price = self._money(payload.get("total_price"))
        if (
            items_subtotal != calculated_subtotal
            or delivery_price < 0
            or total_price != items_subtotal + delivery_price
        ):
            raise InvalidNotificationPayloadError("Invalid order payment notification totals")
        return RenderedEmail(
            recipient=recipient,
            subject=f"Заказ #{order_id} оплачен — garment-buro",
            html=self.order_payment_confirmed_template.render(
                order_id=order_id,
                first_name=first_name,
                items=rendered_items,
                items_subtotal=f"{items_subtotal:.2f}",
                delivery_price=f"{delivery_price:.2f}",
                total_price=f"{total_price:.2f}",
            ),
        )

    @staticmethod
    def _money(value: object) -> Decimal:
        if not isinstance(value, str) or len(value) > 32:
            raise InvalidNotificationPayloadError("Invalid notification money value")
        try:
            amount = Decimal(value)
        except InvalidOperation as error:
            raise InvalidNotificationPayloadError("Invalid notification money value") from error
        if (
            not amount.is_finite()
            or amount < 0
            or amount > Decimal("9999999999.99")
            or amount.as_tuple().exponent < -2
        ):
            raise InvalidNotificationPayloadError("Invalid notification money value")
        return amount

    @staticmethod
    def _bounded_text(value: object, *, maximum: int) -> bool:
        return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum

    @classmethod
    def _optional_bounded_text(cls, value: object, *, maximum: int) -> bool:
        return value is None or value == "" or cls._bounded_text(value, maximum=maximum)
