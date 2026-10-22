from sqlalchemy import func, select

from app.extensions import db
from app.models import ContactMessage, Order, Product, ProductVariant, User
from app.models.constants import (CONTACT_NEW, ORDER_COMPLETED, ORDER_PENDING, ORDER_SHIPPING,
                                  PAYMENT_PAID, PROCESSING_STATUSES, ROLE_CUSTOMER)


def customer_stats(user):
    rows = db.session.execute(
        select(Order.order_status, func.count(Order.id)).where(Order.user_id == user.id)
        .group_by(Order.order_status)).all()
    counts = {status: n for status, n in rows}
    return {
        "total": sum(counts.values()),
        "processing": sum(counts.get(s, 0) for s in PROCESSING_STATUSES),
        "shipping": counts.get(ORDER_SHIPPING, 0),
        "completed": counts.get(ORDER_COMPLETED, 0),
    }


def recent_orders(user, limit=5):
    return db.session.scalars(
        select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc(), Order.id.desc())
        .limit(limit)).all()


def admin_stats(low_stock_threshold=5):
    scalar = db.session.scalar
    return {
        "customers": scalar(select(func.count(User.id)).where(User.role == ROLE_CUSTOMER)) or 0,
        "products": scalar(select(func.count(Product.id))) or 0,
        "orders": scalar(select(func.count(Order.id))) or 0,
        "pending_orders": scalar(select(func.count(Order.id)).where(Order.order_status == ORDER_PENDING)) or 0,
        "revenue_paid": scalar(select(func.coalesce(func.sum(Order.total_amount), 0))
                               .where(Order.payment_status == PAYMENT_PAID)) or 0,
        "low_stock": scalar(select(func.count(ProductVariant.id))
                            .where(ProductVariant.stock_quantity <= low_stock_threshold)) or 0,
        "new_contacts": scalar(select(func.count(ContactMessage.id))
                               .where(ContactMessage.status == CONTACT_NEW)) or 0,
    }
