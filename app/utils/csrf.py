"""CSRF bảo vệ bằng token lưu trong session (không phụ thuộc thư viện ngoài)."""
import hmac
import secrets

from flask import abort, current_app, request, session

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def generate_csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def protect_csrf():
    """Dùng với app.before_request."""
    if not current_app.config.get("CSRF_ENABLED", True):
        return
    if request.method in SAFE_METHODS:
        return
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRFToken", "")
    expected = session.get("_csrf_token", "")
    if not expected or not hmac.compare_digest(str(sent), expected):
        abort(400, description="Phiên làm việc không hợp lệ hoặc đã hết hạn. Vui lòng tải lại trang và thử lại.")
