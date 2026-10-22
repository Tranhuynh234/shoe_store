import hashlib
import secrets
from datetime import timedelta

from flask import request
from sqlalchemy import delete, func, select

from app.extensions import db
from app.models import RateLimitEvent
from app.models.base import utcnow


def client_ip() -> str:
    return (request.remote_addr or "unknown")[:45]


def _bucket(name: str, ident: str) -> str:
    return hashlib.sha256(f"{name}:{ident}".encode("utf-8")).hexdigest()


def is_blocked(name: str, ident: str, limit: int, window_seconds: int) -> bool:
    since = utcnow() - timedelta(seconds=window_seconds)
    n = db.session.scalar(select(func.count(RateLimitEvent.id)).where(
        RateLimitEvent.bucket == _bucket(name, ident), RateLimitEvent.created_at >= since)) or 0
    return n >= limit


def record(name: str, ident: str) -> None:
    db.session.add(RateLimitEvent(bucket=_bucket(name, ident), created_at=utcnow()))
    if secrets.randbelow(100) == 0:
        db.session.execute(delete(RateLimitEvent).where(RateLimitEvent.created_at < utcnow() - timedelta(days=1)))


def clear(name: str, ident: str) -> None:
    db.session.execute(delete(RateLimitEvent).where(RateLimitEvent.bucket == _bucket(name, ident)))