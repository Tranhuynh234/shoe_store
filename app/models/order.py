from decimal import Decimal

from app.extensions import db
from .base import TimestampMixin, utcnow
from .constants import (ORDER_PENDING, ORDER_STATUS_LABELS, PAYMENT_METHOD_COD, PAYMENT_STATUS_LABELS,
                        PAYMENT_UNPAID, PAYMENT_METHOD_LABELS)

_OPTS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class Cart(TimestampMixin, db.Model):
    __tablename__ = "carts"
    __table_args__ = (_OPTS,)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)  

    user = db.relationship("User", back_populates="cart")
    items = db.relationship("CartItem", back_populates="cart", cascade="all, delete-orphan",
                            order_by="CartItem.id")


class CartItem(db.Model):
    __tablename__ = "cart_items"
    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="ck_cart_items_qty"),
        db.UniqueConstraint("cart_id", "product_variant_id", name="uq_cart_variant"),
        _OPTS,
    )

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True)
    product_variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id", ondelete="CASCADE"),
                                   nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    cart = db.relationship("Cart", back_populates="items")
    variant = db.relationship("ProductVariant")


class Order(TimestampMixin, db.Model):
    __tablename__ = "orders"
    __table_args__ = (
        db.CheckConstraint("subtotal >= 0 AND shipping_fee >= 0 AND discount_amount >= 0 AND total_amount >= 0",
                           name="ck_orders_amounts"),
        db.CheckConstraint("order_status IN ('PENDING','CONFIRMED','SHIPPING','COMPLETED','CANCELLED')",
                           name="ck_orders_status"),
        db.CheckConstraint("payment_status IN ('UNPAID','PAID','FAILED','REFUNDED')", name="ck_orders_pay_status"),
        db.Index("ix_orders_user_created", "user_id", "created_at"),
        _OPTS,
    )

    id = db.Column(db.Integer, primary_key=True)
    order_code = db.Column(db.String(32), nullable=False, unique=True)
    # RESTRICT: không xóa được người dùng đã có đơn (dùng is_active=False để khóa tài khoản)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    address_id = db.Column(db.Integer, db.ForeignKey("addresses.id", ondelete="SET NULL"))
    # Ảnh chụp địa chỉ giao hàng tại thời điểm đặt (không đổi khi khách sửa/xóa địa chỉ)
    ship_name = db.Column(db.String(120), nullable=False)
    ship_phone = db.Column(db.String(20), nullable=False)
    ship_address = db.Column(db.String(500), nullable=False)
    subtotal = db.Column(db.Numeric(12, 0), nullable=False)
    shipping_fee = db.Column(db.Numeric(12, 0), nullable=False, default=0)
    discount_amount = db.Column(db.Numeric(12, 0), nullable=False, default=0)
    total_amount = db.Column(db.Numeric(12, 0), nullable=False)
    payment_method = db.Column(db.String(20), nullable=False, default=PAYMENT_METHOD_COD)
    payment_status = db.Column(db.String(20), nullable=False, default=PAYMENT_UNPAID)
    order_status = db.Column(db.String(20), nullable=False, default=ORDER_PENDING, index=True)
    customer_note = db.Column(db.String(500))

    user = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id")
    payments = db.relationship("Payment", back_populates="order", cascade="all, delete-orphan",
                               order_by="Payment.id")

    @property
    def status_label(self) -> str:
        return ORDER_STATUS_LABELS.get(self.order_status, self.order_status)

    @property
    def payment_status_label(self) -> str:
        return PAYMENT_STATUS_LABELS.get(self.payment_status, self.payment_status)

    @property
    def payment_method_label(self) -> str:
        return PAYMENT_METHOD_LABELS.get(self.payment_method, self.payment_method)

    @property
    def item_count(self) -> int:
        return sum(i.quantity for i in self.items)
    
    @property
    def is_guest(self) -> bool:
        return self.user_id is None


class OrderItem(db.Model):
    __tablename__ = "order_items"
    __table_args__ = (
        db.CheckConstraint("quantity > 0 AND unit_price >= 0 AND subtotal >= 0", name="ck_order_items_values"),
        _OPTS,
    )

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    # SET NULL: xóa biến thể/sản phẩm không làm mất lịch sử đơn (đã có ảnh chụp bên dưới)
    product_variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id", ondelete="SET NULL"))
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="SET NULL"), index=True)
    product_name = db.Column(db.String(200), nullable=False)
    product_code = db.Column(db.String(50), nullable=False)
    size = db.Column(db.String(20), nullable=False)
    color = db.Column(db.String(50), nullable=False, default="")
    unit_price = db.Column(db.Numeric(12, 0), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Numeric(12, 0), nullable=False)

    order = db.relationship("Order", back_populates="items")
    variant = db.relationship("ProductVariant")
    product = db.relationship("Product")


class Payment(db.Model):
    __tablename__ = "payments"
    __table_args__ = (
        db.CheckConstraint("amount >= 0", name="ck_payments_amount"),
        db.CheckConstraint("payment_status IN ('UNPAID','PAID','FAILED','REFUNDED')", name="ck_payments_status"),
        _OPTS,
    )

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_method = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(12, 0), nullable=False)
    # Chỉ lưu mã do nhà cung cấp/nhân viên xác minh nhập; hệ thống KHÔNG tự sinh mã giao dịch.
    transaction_code = db.Column(db.String(100))
    payment_status = db.Column(db.String(20), nullable=False, default=PAYMENT_UNPAID)
    verification_note = db.Column(db.String(500))
    paid_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    order = db.relationship("Order", back_populates="payments")
