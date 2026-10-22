"""Tài khoản khách hàng/quản trị; đăng nhập bằng số điện thoại, không dùng email."""
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from .base import TimestampMixin

_OPTS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint("role IN ('CUSTOMER','ADMIN')", name="ck_users_role"),
        _OPTS,
    )

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False, default="Khách hàng")
    phone = db.Column(db.String(20), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="CUSTOMER")
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    addresses = db.relationship("Address", back_populates="user", cascade="all, delete-orphan",
                                order_by="Address.id")
    cart = db.relationship("Cart", back_populates="user", uselist=False, cascade="all, delete-orphan")
    orders = db.relationship("Order", back_populates="user")

    @property
    def is_admin(self):
        return self.role == "ADMIN"

    @property
    def default_address(self):
        return next((a for a in self.addresses if a.is_default), None)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Address(TimestampMixin, db.Model):
    __tablename__ = "addresses"
    __table_args__ = (_OPTS,)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    province = db.Column(db.String(100), nullable=False)
    district = db.Column(db.String(100), nullable=False)
    ward = db.Column(db.String(100), nullable=False)
    address_detail = db.Column(db.String(255), nullable=False)
    is_default = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship("User", back_populates="addresses")

    @property
    def full_text(self):
        return ", ".join(p for p in (self.address_detail, self.ward, self.district, self.province) if p)
