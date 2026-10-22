"""Dữ liệu xác thực bằng SĐT: OTP khôi phục mật khẩu và bộ đếm giới hạn tần suất."""
from app.extensions import db
from .base import utcnow

_OPTS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class PasswordResetOTP(db.Model):
    __tablename__ = "password_reset_otps"
    __table_args__ = (db.Index("ix_pwotp_phone_created", "phone", "created_at"), _OPTS)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False)
    salt = db.Column(db.String(32), nullable=False)
    code_hash = db.Column(db.String(64), nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    expires_at = db.Column(db.DateTime, nullable=False)
    verified_at = db.Column(db.DateTime)
    reset_token_hash = db.Column(db.String(64))
    reset_token_expires_at = db.Column(db.DateTime)
    consumed_at = db.Column(db.DateTime)
    request_ip = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class RateLimitEvent(db.Model):
    __tablename__ = "rate_limit_events"
    __table_args__ = (db.Index("ix_rate_bucket_created", "bucket", "created_at"), _OPTS)

    id = db.Column(db.Integer, primary_key=True)
    bucket = db.Column(db.String(64), nullable=False)  # sha256(tên:giá trị)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)