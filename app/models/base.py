from datetime import datetime, timezone

from app.extensions import db


def utcnow() -> datetime:
    """Thời gian UTC không kèm tzinfo (MySQL DATETIME không lưu timezone)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
