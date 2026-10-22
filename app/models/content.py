from app.extensions import db
from .base import utcnow
from .constants import CONTACT_NEW, POST_DRAFT

_OPTS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class Review(db.Model):
    __tablename__ = "reviews"
    __table_args__ = (
        db.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),
        db.UniqueConstraint("order_item_id", name="uq_reviews_order_item"),
        _OPTS,
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey("order_items.id", ondelete="SET NULL"))
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User")
    product = db.relationship("Product", backref=db.backref("reviews", cascade="all, delete-orphan"))


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    __table_args__ = (
        db.CheckConstraint("status IN ('DRAFT','PUBLISHED')", name="ck_blog_status"),
        db.Index("ix_blog_status_published", "status", "published_at"),
        _OPTS,
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), nullable=False, unique=True)
    summary = db.Column(db.String(500))
    content = db.Column(db.Text, nullable=False)
    thumbnail = db.Column(db.String(255))
    status = db.Column(db.String(20), nullable=False, default=POST_DRAFT)
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"
    __table_args__ = (
        db.CheckConstraint("status IN ('NEW','READ','RESOLVED')", name="ck_contact_status"),
        _OPTS,
    )

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=CONTACT_NEW, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
