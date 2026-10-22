from decimal import Decimal

from flask import current_app
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Cart, CartItem, Product, ProductVariant
from app.services import BusinessError


def get_cart(user, create=False):
    cart = db.session.scalar(
        select(Cart).where(Cart.user_id == user.id)
        .options(selectinload(Cart.items).selectinload(CartItem.variant)
                 .selectinload(ProductVariant.product).selectinload(Product.images)))
    if cart is None and create:
        cart = Cart(user_id=user.id)
        db.session.add(cart)
        db.session.flush()
    return cart


def cart_quantity(user) -> int:
    cart = db.session.scalar(select(Cart).where(Cart.user_id == user.id))
    if not cart:
        return 0
    from sqlalchemy import func
    return int(db.session.scalar(select(func.coalesce(func.sum(CartItem.quantity), 0))
                                 .where(CartItem.cart_id == cart.id)) or 0)


def _check_variant(variant_id):
    variant = db.session.get(ProductVariant, variant_id) if variant_id else None
    if variant is None or not variant.product.is_active:
        raise BusinessError("Sản phẩm hoặc kích cỡ không tồn tại hoặc đã ngừng bán.")
    return variant


def add_item(user, variant_id, quantity):
    max_qty = current_app.config["MAX_QTY_PER_ITEM"]
    if not isinstance(quantity, int) or quantity < 1 or quantity > max_qty:
        raise BusinessError(f"Số lượng phải từ 1 đến {max_qty}.")
    variant = _check_variant(variant_id)
    cart = get_cart(user, create=True)
    item = next((i for i in cart.items if i.product_variant_id == variant.id), None)
    new_qty = (item.quantity if item else 0) + quantity
    if new_qty > variant.stock_quantity:
        raise BusinessError(f"Chỉ còn {variant.stock_quantity} sản phẩm ({variant.label}) trong kho.")
    if new_qty > max_qty:
        raise BusinessError(f"Mỗi sản phẩm tối đa {max_qty} cái trong giỏ.")
    if item:
        item.quantity = new_qty
    else:
        db.session.add(CartItem(cart_id=cart.id, product_variant_id=variant.id, quantity=new_qty))
    db.session.commit()


def _owned_item(user, item_id):
    item = db.session.get(CartItem, item_id) if item_id else None
    if item is None or item.cart.user_id != user.id:
        raise BusinessError("Không tìm thấy sản phẩm trong giỏ hàng.")
    return item


def update_item(user, item_id, quantity):
    item = _owned_item(user, item_id)
    if not isinstance(quantity, int) or quantity < 1:
        raise BusinessError("Số lượng không hợp lệ. Dùng nút xóa để bỏ sản phẩm.")
    if quantity > current_app.config["MAX_QTY_PER_ITEM"]:
        raise BusinessError(f"Mỗi sản phẩm tối đa {current_app.config['MAX_QTY_PER_ITEM']} cái.")
    if quantity > item.variant.stock_quantity:
        raise BusinessError(f"Chỉ còn {item.variant.stock_quantity} sản phẩm trong kho.")
    item.quantity = quantity
    db.session.commit()


def remove_item(user, item_id):
    item = _owned_item(user, item_id)
    db.session.delete(item)
    db.session.commit()


def shipping_fee_for(subtotal) -> Decimal:
    subtotal = Decimal(subtotal)
    if subtotal <= 0:
        return Decimal(0)
    if subtotal >= current_app.config["FREE_SHIPPING_THRESHOLD"]:
        return Decimal(0)
    return Decimal(current_app.config["SHIPPING_FEE"])


def summarize(cart):
    """Tổng tiền tính hoàn toàn ở server từ giá trong database."""
    lines, subtotal, problems = [], Decimal(0), []
    for item in (cart.items if cart else []):
        v = item.variant
        unit = v.product.current_price
        line_total = unit * item.quantity
        subtotal += line_total
        issue = None
        if not v.product.is_active:
            issue = "Sản phẩm đã ngừng bán"
        elif v.stock_quantity < item.quantity:
            issue = f"Chỉ còn {v.stock_quantity} trong kho"
        if issue:
            problems.append(issue)
        lines.append({"item": item, "variant": v, "product": v.product, "unit_price": unit,
                      "line_total": line_total, "issue": issue})
    shipping = shipping_fee_for(subtotal)
    discount = Decimal(0)  # chưa có hệ thống mã giảm giá
    return {"lines": lines, "subtotal": subtotal, "shipping_fee": shipping, "discount": discount,
            "total": subtotal + shipping - discount, "problems": problems,
            "count": sum(l["item"].quantity for l in lines)}
