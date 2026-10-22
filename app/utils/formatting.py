from decimal import Decimal

from markupsafe import Markup, escape

from app.models.constants import (CONTACT_STATUS_LABELS, ORDER_STATUS_LABELS, PAYMENT_STATUS_LABELS)


def vnd(value) -> str:
    if value is None:
        return "—"
    return f"{int(Decimal(value)):,}".replace(",", ".") + " ₫"


def paragraphs(text) -> Markup:
    """Chuyển văn bản thuần thành các đoạn <p>, đã escape (chống XSS)."""
    blocks = [b.strip() for b in (text or "").replace("\r\n", "\n").split("\n\n") if b.strip()]
    html = "".join("<p>" + str(escape(b)).replace("\n", "<br>") + "</p>" for b in blocks)
    return Markup(html)


def order_status_label(code):
    return ORDER_STATUS_LABELS.get(code, code)


def payment_status_label(code):
    return PAYMENT_STATUS_LABELS.get(code, code)


def contact_status_label(code):
    return CONTACT_STATUS_LABELS.get(code, code)


def dt(value, fmt="%d/%m/%Y %H:%M"):
    return value.strftime(fmt) if value else "—"
