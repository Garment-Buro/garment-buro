from __future__ import annotations

import json
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Template

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

AUTH_TEMPLATE = """
<html>
<body style="font-family: 'Inter', sans-serif; background-color: #f7f7f7; padding: 40px;">
    <div style="max-width: 500px; margin: 0 auto; background-color: #ffffff; padding: 40px; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.05);">
        <h1 style="font-size: 24px; color: #000; margin-bottom: 20px; text-align: center;">Код подтверждения</h1>
        <p style="font-size: 16px; color: #666; text-align: center; margin-bottom: 30px;">
            Используйте этот код для входа или регистрации на сайте garment-buro.
        </p>
        <div style="background-color: #f2f2f2; padding: 20px; text-align: center; border-radius: 12px;">
            <span style="font-size: 32px; font-weight: 700; letter-spacing: 5px; color: #000;">{{ code }}</span>
        </div>
        <p style="font-size: 12px; color: #999; text-align: center; margin-top: 30px;">
            Если вы не запрашивали этот код, просто проигнорируйте это письмо.
        </p>
    </div>
</body>
</html>
"""

ORDER_TEMPLATE = """
<html>
<body style="font-family: 'Inter', sans-serif; background-color: #f7f7f7; color: #000; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 40px; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.05);">
        <h1 style="font-size: 24px; margin-bottom: 20px; text-align: center;">Заказ #{{ order_id }} подтвержден!</h1>
        <p style="font-size: 16px; color: #444; margin-bottom: 30px; text-align: center;">
            Спасибо за ваш заказ в garment-buro. Мы уже начали его обработку.
        </p>
        
        <div style="border-top: 1px solid #eee; padding-top: 20px; margin-bottom: 30px;">
            <h2 style="font-size: 18px; margin-bottom: 15px;">Детали заказа:</h2>
            <table style="width: 100%; border-collapse: collapse;">
                {% for item in items %}
                <tr style="border-bottom: 1px solid #f2f2f2;">
                    <td style="padding: 10px 0;">
                        <span style="font-weight: 600;">{{ item.title }}</span><br/>
                        <span style="font-size: 12px; color: #666;">Размер: {{ item.size or 'N/A' }}, Цвет: {{ item.color or 'N/A' }}</span>
                    </td>
                    <td style="text-align: right; padding: 10px 0;">
                        {{ item.quantity }} x {{ item.price }} ₽
                    </td>
                </tr>
                {% endfor %}
            </table>
            <div style="text-align: right; margin-top: 20px; font-size: 18px; font-weight: 700;">
                Итого: {{ total_price }} ₽
            </div>
        </div>

        <div style="background-color: #f9f9f9; padding: 20px; border-radius: 12px; margin-bottom: 30px;">
            <h3 style="font-size: 14px; margin-top: 0;">Адрес доставки:</h3>
            <p style="font-size: 14px; margin-bottom: 0;">{{ delivery_address }}</p>
        </div>

        <div style="text-align: center;">
            <a href="{{ view_url }}" target="_blank" style="display: inline-block; background-color: #000; color: #fff; padding: 16px 32px; border-radius: 12px; text-decoration: none; font-weight: 600;">Посмотреть детали заказа</a>
        </div>
    </div>
</body>
</html>
"""


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    *,
    settings: Settings | None = None,
) -> bool:
    runtime_settings = settings or get_settings()
    smtp_password = Settings.secret_value(runtime_settings.smtp_password)
    if not smtp_password:
        logger.error("SMTP delivery skipped because SMTP_PASSWORD is not configured")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"garment-buro <{runtime_settings.smtp_user}>"
        msg["To"] = to_email

        part = MIMEText(html_content, "html")
        msg.attach(part)

        smtp_class = smtplib.SMTP_SSL if runtime_settings.smtp_use_ssl else smtplib.SMTP
        with smtp_class(
            runtime_settings.smtp_server,
            runtime_settings.smtp_port,
            timeout=15,
        ) as server:
            if not runtime_settings.smtp_use_ssl:
                server.starttls()
            server.login(runtime_settings.smtp_user, smtp_password)
            server.sendmail(
                runtime_settings.smtp_user,
                to_email,
                msg.as_string(),
            )

        logger.info("Email delivery completed")
        return True
    except (OSError, smtplib.SMTPException):
        logger.exception("Email delivery failed")
        return False


def send_auth_otp(email: str, code: str) -> bool:
    template = Template(AUTH_TEMPLATE)
    html = template.render(code=code)
    return send_email(email, f"{code} — ваш код для garment-buro", html)


def send_order_confirmation(order) -> bool:
    if not order.email:
        logger.info("Order confirmation skipped because the order has no email")
        return False

    try:
        items = json.loads(order.cart_items) if order.cart_items else []
    except (json.JSONDecodeError, TypeError):
        items = []

    runtime_settings = get_settings()
    template = Template(ORDER_TEMPLATE)
    html = template.render(
        order_id=order.id,
        items=items,
        total_price=order.total_price,
        delivery_address=order.delivery_address,
        view_url=f"{runtime_settings.public_base_url.rstrip('/')}/order/{order.id}",
    )

    return send_email(order.email, f"Ваш заказ #{order.id} оформлен", html)
