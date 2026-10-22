from decimal import Decimal

from app.extensions import db
from .base import TimestampMixin

_OPTS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class Category(db.Model):
    __tablename__ = "categories"
    __table_args__ = (_OPTS,)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    products = db.relationship("Product", back_populates="category")


class Brand(db.Model):
    __tablename__ = "brands"
    __table_args__ = (_OPTS,)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text)
    # Đường dẫn tương đối trong thư mục static, ví dụ "images/logo-tuan.png"
    logo = db.Column(db.String(255))
    # Ảnh đại diện thương hiệu hiển thị ở trang chủ (bổ sung so với yêu cầu tối thiểu)
    cover_image = db.Column(db.String(255))

    products = db.relationship("Product", back_populates="brand")


class Product(TimestampMixin, db.Model):
    __tablename__ = "products"
    __table_args__ = (
        db.CheckConstraint("price >= 0", name="ck_products_price"),
        db.CheckConstraint("sale_price IS NULL OR (sale_price >= 0 AND sale_price <= price)",
                           name="ck_products_sale_price"),
        db.Index("ix_products_active_category_brand", "is_active", "category_id", "brand_id"),
        _OPTS,
    )

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id", ondelete="RESTRICT"))
    name = db.Column(db.String(200), nullable=False, index=True)
    slug = db.Column(db.String(220), nullable=False, unique=True)
    product_code = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.Text)
    material = db.Column(db.String(255))
    origin = db.Column(db.String(100))
    price = db.Column(db.Numeric(12, 0), nullable=False)
    sale_price = db.Column(db.Numeric(12, 0))
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    category = db.relationship("Category", back_populates="products")
    brand = db.relationship("Brand", back_populates="products")
    images = db.relationship("ProductImage", back_populates="product", cascade="all, delete-orphan",
                             order_by="ProductImage.is_primary.desc(), ProductImage.sort_order, ProductImage.id")
    variants = db.relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan",
                               order_by="ProductVariant.size, ProductVariant.color")

    @property
    def current_price(self) -> Decimal:
        return self.sale_price if self.sale_price is not None else self.price

    @property
    def on_sale(self) -> bool:
        return self.sale_price is not None and self.sale_price < self.price

    @property
    def discount_percent(self) -> int:
        if not self.on_sale or not self.price:
            return 0
        return int((self.price - self.sale_price) * 100 / self.price)

    @property
    def primary_image(self):
        return self.images[0] if self.images else None

    @property
    def total_stock(self) -> int:
        return sum(v.stock_quantity for v in self.variants)

    @property
    def in_stock(self) -> bool:
        return self.total_stock > 0


class ProductImage(db.Model):
    __tablename__ = "product_images"
    __table_args__ = (_OPTS,)

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    # Đường dẫn tương đối trong static, ví dụ "uploads/products/abc.jpg"
    image_url = db.Column(db.String(255), nullable=False)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    product = db.relationship("Product", back_populates="images")


class ProductVariant(db.Model):
    __tablename__ = "product_variants"
    __table_args__ = (
        db.CheckConstraint("stock_quantity >= 0", name="ck_variants_stock"),
        db.UniqueConstraint("product_id", "size", "color", name="uq_variant_product_size_color"),
        _OPTS,
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    size = db.Column(db.String(20), nullable=False)
    # Chuỗi rỗng = màu mặc định (tránh NULL làm hỏng ràng buộc UNIQUE)
    color = db.Column(db.String(50), nullable=False, default="")
    sku = db.Column(db.String(80), nullable=False, unique=True)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)

    product = db.relationship("Product", back_populates="variants")

    @property
    def label(self) -> str:
        return f"Size {self.size}" + (f" / {self.color}" if self.color else "")
