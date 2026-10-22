import secrets
from datetime import datetime, timezone
from decimal import Decimal

from flask import current_app
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Address, Order, OrderItem, Payment, ProductVariant
from app.models.base import utcnow
from app.models.constants import (ORDER_CANCELLED, ORDER_COMPLETED, ORDER_PENDING, ORDER_SHIPPING,
                                  ORDER_TRANSITIONS, PAYMENT_FAILED, PAYMENT_PAID, PAYMENT_REFUNDED,
                                  PAYMENT_STATUSES, PAYMENT_UNPAID)
from app.services import BusinessError, cart_service
from app.utils.validators import clean


def _new_order_code() -> str:
    return "GT" + datetime.now(timezone.utc).strftime("%y%m%d") + secrets.token_hex(3).upper()


def create_order(user, address_id, payment_method="COD", note=None) -> Order:
    """Tạo đơn trong MỘT transaction: kiểm tồn kho nguyên tử, lưu snapshot, xóa giỏ."""
    if payment_method not in current_app.config["ENABLED_PAYMENT_METHODS"]:
        raise BusinessError("Phương thức thanh toán này hiện chưa được hỗ trợ.")
    address = db.session.get(Address, address_id) if address_id else None
    if address is None or address.user_id != user.id:
        raise BusinessError("Vui lòng chọn địa chỉ giao hàng hợp lệ.")
    cart = cart_service.get_cart(user)
    if cart is None or not cart.items:
        raise BusinessError("Giỏ hàng của bạn đang trống.")

    try:
        subtotal = Decimal(0)
        order_items = []
        # Sắp xếp theo id để mọi giao dịch khóa dòng cùng thứ tự (tránh deadlock)
        for ci in sorted(cart.items, key=lambda i: i.product_variant_id):
            variant, product = ci.variant, ci.variant.product
            if not product.is_active:
                raise BusinessError(f"Sản phẩm «{product.name}» hiện không còn bán. Vui lòng xóa khỏi giỏ.")
            # Trừ kho nguyên tử: chỉ thành công nếu còn đủ hàng ở thời điểm UPDATE
            result = db.session.execute(
                update(ProductVariant)
                .where(ProductVariant.id == variant.id, ProductVariant.stock_quantity >= ci.quantity)
                .values(stock_quantity=ProductVariant.stock_quantity - ci.quantity))
            if result.rowcount != 1:
                raise BusinessError(f"«{product.name}» ({variant.label}) không đủ số lượng tồn kho.")
            unit = product.current_price  # giá lấy từ DB, không từ trình duyệt
            line = unit * ci.quantity
            subtotal += line
            order_items.append(OrderItem(
                product_variant_id=variant.id, product_id=product.id, product_name=product.name,
                product_code=product.product_code, size=variant.size, color=variant.color,
                unit_price=unit, quantity=ci.quantity, subtotal=line))
        shipping = cart_service.shipping_fee_for(subtotal)
        discount = Decimal(0)
        total = subtotal + shipping - discount
        order = Order(
            order_code=_new_order_code(), user_id=user.id, address_id=address.id,
            ship_name=address.recipient_name, ship_phone=address.phone, ship_address=address.full_text,
            subtotal=subtotal, shipping_fee=shipping, discount_amount=discount, total_amount=total,
            payment_method=payment_method, payment_status=PAYMENT_UNPAID, order_status=ORDER_PENDING,
            customer_note=clean(note, 500) or None)
        order.items = order_items
        order.payments.append(Payment(payment_method=payment_method, amount=total, payment_status=PAYMENT_UNPAID))
        db.session.add(order)
        for ci in list(cart.items):
            db.session.delete(ci)
        db.session.commit()
        return order
    except BusinessError:
        db.session.rollback()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Lỗi database khi tạo đơn hàng (user_id=%s)", user.id)
        raise BusinessError("Không thể tạo đơn hàng lúc này. Vui lòng thử lại sau.")


def get_user_order(user, order_code):
    return db.session.scalar(
        select(Order).where(Order.order_code == order_code, Order.user_id == user.id)
        .options(selectinload(Order.items), selectinload(Order.payments)))


def _restore_stock(order: Order):
    for item in order.items:
        if item.product_variant_id:
            db.session.execute(
                update(ProductVariant).where(ProductVariant.id == item.product_variant_id)
                .values(stock_quantity=ProductVariant.stock_quantity + item.quantity))


def _cancel(order: Order):
    _restore_stock(order)
    order.order_status = ORDER_CANCELLED
    if order.payment_status == PAYMENT_UNPAID:
        order.payment_status = PAYMENT_FAILED
        for p in order.payments:
            if p.payment_status == PAYMENT_UNPAID:
                p.payment_status = PAYMENT_FAILED


def cancel_order_by_customer(user, order_code):
    order = get_user_order(user, order_code)
    if order is None:
        raise BusinessError("Không tìm thấy đơn hàng.")
    if order.order_status != ORDER_PENDING:
        raise BusinessError("Chỉ có thể hủy đơn đang ở trạng thái «Chờ xác nhận».")
    _cancel(order)
    db.session.commit()
    return order


def admin_update_status(order: Order, new_status: str):
    if new_status not in ORDER_TRANSITIONS.get(order.order_status, ()):
        raise BusinessError("Không thể chuyển trạng thái đơn hàng theo hướng này.")
    if new_status == ORDER_CANCELLED:
        if order.payment_status == PAYMENT_PAID:
            raise BusinessError("Đơn đã thanh toán, cần xử lý hoàn tiền trước khi hủy.")
        _cancel(order)
    else:
        order.order_status = new_status
    db.session.commit()


def admin_update_payment(order: Order, new_status: str, note: str, transaction_code: str = ""):
    """Đánh dấu thanh toán chỉ khi có ghi chú xác minh của nhân viên; không tự sinh mã giao dịch."""
    note, transaction_code = clean(note, 500), clean(transaction_code, 100)
    if new_status not in PAYMENT_STATUSES:
        raise BusinessError("Trạng thái thanh toán không hợp lệ.")
    if order.order_status == ORDER_CANCELLED:
        raise BusinessError("Đơn đã hủy, không thể cập nhật thanh toán.")
    if new_status == PAYMENT_PAID:
        if order.payment_status == PAYMENT_PAID:
            raise BusinessError("Đơn đã được đánh dấu thanh toán.")
        if order.order_status not in (ORDER_SHIPPING, ORDER_COMPLETED):
            raise BusinessError("Với COD, chỉ xác nhận đã thu tiền khi đơn đang giao hoặc đã hoàn thành.")
        if not note:
            raise BusinessError("Cần nhập ghi chú xác minh (ví dụ: nhân viên giao hàng đã thu đủ tiền).")
    elif new_status == PAYMENT_REFUNDED:
        if order.payment_status != PAYMENT_PAID:
            raise BusinessError("Chỉ hoàn tiền được cho đơn đã thanh toán.")
        if not note:
            raise BusinessError("Cần nhập ghi chú xác minh hoàn tiền.")
    order.payment_status = new_status
    payment = order.payments[-1] if order.payments else None
    if payment is None:
        payment = Payment(order_id=order.id, payment_method=order.payment_method, amount=order.total_amount)
        order.payments.append(payment)
    payment.payment_status = new_status
    payment.verification_note = note or payment.verification_note
    if transaction_code:
        payment.transaction_code = transaction_code
    payment.paid_at = utcnow() if new_status == PAYMENT_PAID else payment.paid_at
    db.session.commit()
