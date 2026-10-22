"""Sản phẩm đã xem gần đây: lưu id trong session (cookie đã ký), không cần đăng nhập."""
from flask import session
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Product

KEY = "recent_products"
MAX_STORED = 12


def remember(product_id: int) -> None:
    ids = [i for i in session.get(KEY, []) if i != product_id]
    ids.insert(0, product_id)
    session[KEY] = ids[:MAX_STORED]


def clear() -> None:
    session.pop(KEY, None)


def recently_viewed(exclude_id=None, limit=6):
    ids = [i for i in session.get(KEY, []) if isinstance(i, int) and i != exclude_id][:limit]
    if not ids:
        return []
    products = db.session.scalars(
        select(Product).where(Product.id.in_(ids), Product.is_active.is_(True))
        .options(selectinload(Product.images), selectinload(Product.variants), selectinload(Product.brand))).all()
    order = {pid: n for n, pid in enumerate(ids)}
    return sorted(products, key=lambda p: order[p.id])