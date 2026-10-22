"""Đăng nhập/đăng ký bằng số điện thoại và khôi phục mật khẩu bằng SMS OTP."""
import hashlib
import secrets
from datetime import timedelta

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import PasswordResetOTP, User
from app.models.base import utcnow
from app.models.constants import ROLE_ADMIN
from app.services import BusinessError, auth_service, rate_limit_service
from app.services.sms_service import SmsError, send_otp
from app.utils.validators import clean, normalize_phone, valid_phone, validate_password

bp = Blueprint("auth", __name__)


def _json_request():
    return request.is_json


def _response_error(message, status=400):
    return (jsonify({"error": message}), status) if _json_request() else None


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard" if current_user.is_admin else "account.dashboard"))
    if request.method == "GET":
        return render_template("auth/login.html", next=request.args.get("next", ""))
    phone = normalize_phone(clean(request.form.get("phone") or request.form.get("phone_number"), 20))
    password = request.form.get("password", "")
    ip = rate_limit_service.client_ip()
    if rate_limit_service.is_blocked("login_ip", ip, current_app.config["LOGIN_MAX_FAILS_PER_IP"],
                                     current_app.config["LOGIN_WINDOW_SECONDS"]) or rate_limit_service.is_blocked(
            "login_phone", phone, current_app.config["LOGIN_MAX_FAILS_PER_PHONE"],
            current_app.config["LOGIN_WINDOW_SECONDS"]):
        flash("Bạn đã thử đăng nhập quá nhiều lần. Vui lòng thử lại sau.", "error")
        return render_template("auth/login.html", next=request.form.get("next", "")), 429
    user = auth_service.authenticate(phone, password)
    if not user:
        rate_limit_service.record("login_ip", ip)
        rate_limit_service.record("login_phone", phone)
        db.session.commit()
        flash("Số điện thoại hoặc mật khẩu không chính xác.", "error")
        return render_template("auth/login.html", next=request.form.get("next", "")), 401
    if not user.is_active:
        flash("Tài khoản của bạn đã bị khóa.", "error")
        return render_template("auth/login.html"), 403
    login_user(user, remember=bool(request.form.get("remember")))
    target = request.form.get("next", "")
    from app.utils.validators import is_safe_redirect
    if is_safe_redirect(target):
        return redirect(target)
    return redirect(url_for("admin.dashboard" if user.is_admin else "account.dashboard"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account.dashboard"))
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        ip = rate_limit_service.client_ip()
        if rate_limit_service.is_blocked("register_ip", ip, current_app.config["REGISTER_MAX_PER_IP_HOUR"], 3600):
            flash("Bạn thao tác quá nhanh. Vui lòng thử lại sau.", "error")
            return render_template("auth/register.html", form=form), 429
        rate_limit_service.record("register_ip", ip)
        db.session.commit()
        try:
            auth_service.register_user(
                clean(request.form.get("full_name"), 120) or "Khách hàng",
                request.form.get("phone"), request.form.get("password"),
                request.form.get("confirm_password"))
            flash("Đăng ký thành công. Vui lòng đăng nhập.", "success")
            return redirect(url_for("auth.login"))
        except BusinessError as exc:
            errors = exc.args[0] if exc.args else ["Dữ liệu không hợp lệ."]
            for msg in (errors if isinstance(errors, list) else [errors]):
                flash(msg, "error")
    return render_template("auth/register.html", form=form)


@bp.route("/logout", methods=["GET", "POST"])
def logout():
    logout_user()
    session.clear()
    flash("Bạn đã đăng xuất.", "success")
    return redirect(url_for("main.home"))


def _find_reset(phone):
    return db.session.scalar(select(PasswordResetOTP).where(
        PasswordResetOTP.phone == phone, PasswordResetOTP.consumed_at.is_(None)
    ).order_by(PasswordResetOTP.created_at.desc()))


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("auth/forgot_password.html", step="request")
    data = request.get_json(silent=True) or request.form
    phone = normalize_phone(clean(data.get("phone") or data.get("phone_number"), 20))
    ip = rate_limit_service.client_ip()
    message = "Nếu số điện thoại hợp lệ và đã đăng ký, bạn sẽ nhận được hướng dẫn xác minh."
    if not valid_phone(phone):
        return (jsonify({"message": message}), 200) if _json_request() else (render_template("auth/forgot_password.html", step="request", message=message), 200)
    if rate_limit_service.is_blocked("otp_phone", phone, current_app.config["OTP_MAX_SENDS_PER_PHONE_HOUR"], 3600) or rate_limit_service.is_blocked(
            "otp_ip", ip, current_app.config["OTP_MAX_SENDS_PER_IP_HOUR"], 3600):
        return (jsonify({"message": message}), 200) if _json_request() else (render_template("auth/forgot_password.html", step="request", message=message), 200)
    user = db.session.scalar(select(User).where(User.phone == phone, User.is_active.is_(True)))
    if user:
        latest = _find_reset(phone)
        if latest and (utcnow() - latest.created_at).total_seconds() < current_app.config["OTP_RESEND_COOLDOWN"]:
            return (jsonify({"message": message}), 200) if _json_request() else (render_template("auth/forgot_password.html", step="request", message=message), 200)
        code = f"{secrets.randbelow(1_000_000):06d}"
        salt = secrets.token_hex(16)
        row = PasswordResetOTP(user_id=user.id, phone=phone, salt=salt,
            code_hash=hashlib.sha256((salt + code).encode()).hexdigest(),
            attempts=0, expires_at=utcnow() + timedelta(seconds=current_app.config["OTP_TTL_SECONDS"]),
            request_ip=ip)
        db.session.add(row)
        db.session.flush()
        try:
            send_otp(phone, code, max(1, current_app.config["OTP_TTL_SECONDS"] // 60))
            rate_limit_service.record("otp_phone", phone)
            rate_limit_service.record("otp_ip", ip)
            db.session.commit()
        except SmsError:
            db.session.rollback()
            current_app.logger.warning("SMS OTP chưa gửi được; kiểm tra cấu hình nhà cung cấp SMS.")
            if _json_request():
                return jsonify({"message": message, "sms_configured": False}), 503
            return render_template("auth/forgot_password.html", step="request",
                message="Dịch vụ SMS chưa được cấu hình hoặc đang lỗi. Vui lòng thử lại sau."), 503
    return (jsonify({"message": message}), 200) if _json_request() else render_template("auth/forgot_password.html", step="verify", phone=phone, message=message)


@bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json(silent=True) or request.form
    phone = normalize_phone(clean(data.get("phone") or data.get("phone_number"), 20))
    code = clean(data.get("otp") or data.get("otp_code"), 6)
    ip = rate_limit_service.client_ip()
    if rate_limit_service.is_blocked("otp_verify_phone", phone, current_app.config["OTP_MAX_VERIFY_PER_PHONE"], 3600) or rate_limit_service.is_blocked(
            "otp_verify_ip", ip, current_app.config["OTP_MAX_VERIFY_PER_IP"], 3600):
        return jsonify({"error": "Bạn xác minh quá nhiều lần. Vui lòng thử lại sau."}), 429
    rate_limit_service.record("otp_verify_phone", phone)
    rate_limit_service.record("otp_verify_ip", ip)
    db.session.commit()
    row = _find_reset(phone)
    if not row or row.expires_at < utcnow() or row.consumed_at or row.attempts >= current_app.config["OTP_MAX_ATTEMPTS"]:
        msg, status = "Mã OTP không hợp lệ hoặc đã hết hạn.", 400
    else:
        row.attempts += 1
        expected = hashlib.sha256((row.salt + code).encode()).hexdigest()
        if not secrets.compare_digest(row.code_hash, expected):
            db.session.commit()
            msg, status = "Mã OTP không chính xác.", 400
        else:
            token = secrets.token_urlsafe(32)
            row.verified_at = utcnow()
            row.reset_token_hash = hashlib.sha256(token.encode()).hexdigest()
            row.reset_token_expires_at = utcnow() + timedelta(seconds=current_app.config["RESET_TOKEN_TTL_SECONDS"])
            db.session.commit()
            return jsonify({"message": "Xác minh thành công.", "reset_token": token}), 200
    return jsonify({"error": msg}), status


@bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True) or request.form
    phone = normalize_phone(clean(data.get("phone") or data.get("phone_number"), 20))
    token = data.get("reset_token", "")
    password = data.get("new_password") or data.get("password") or ""
    confirm = data.get("confirm_password") or ""
    row = _find_reset(phone)
    if not row or not row.verified_at or row.consumed_at or not row.reset_token_hash or not row.reset_token_expires_at or row.reset_token_expires_at < utcnow() or not secrets.compare_digest(row.reset_token_hash, hashlib.sha256(token.encode()).hexdigest()):
        return jsonify({"error": "Phiên xác minh không hợp lệ hoặc đã hết hạn."}), 403
    err = validate_password(password)
    if err:
        return jsonify({"error": err}), 400
    if password != confirm:
        return jsonify({"error": "Mật khẩu xác nhận không khớp."}), 400
    user = db.session.get(User, row.user_id)
    if not user or user.phone != phone:
        return jsonify({"error": "Không thể cập nhật mật khẩu."}), 400
    user.set_password(password)
    for active in db.session.scalars(select(PasswordResetOTP).where(
            PasswordResetOTP.user_id == user.id, PasswordResetOTP.consumed_at.is_(None))).all():
        active.consumed_at = utcnow()
        active.reset_token_hash = None
    db.session.commit()
    return jsonify({"message": "Đặt lại mật khẩu thành công. Vui lòng đăng nhập."}), 200


@bp.route("/api/auth/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}
    try:
        auth_service.register_user(data.get("full_name") or "Khách hàng", data.get("phone"),
                                   data.get("password"), data.get("confirm_password"))
        return jsonify({"message": "Đăng ký thành công."}), 201
    except BusinessError as exc:
        return jsonify({"error": exc.args[0]}), 400


@bp.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    phone = normalize_phone(clean(data.get("phone"), 20))
    ip = rate_limit_service.client_ip()
    if rate_limit_service.is_blocked("login_ip", ip, current_app.config["LOGIN_MAX_FAILS_PER_IP"], current_app.config["LOGIN_WINDOW_SECONDS"]) or rate_limit_service.is_blocked(
            "login_phone", phone, current_app.config["LOGIN_MAX_FAILS_PER_PHONE"], current_app.config["LOGIN_WINDOW_SECONDS"]):
        return jsonify({"error": "Bạn đã thử đăng nhập quá nhiều lần. Vui lòng thử lại sau."}), 429
    user = auth_service.authenticate(phone, data.get("password"))
    if not user:
        rate_limit_service.record("login_ip", ip)
        rate_limit_service.record("login_phone", phone)
        db.session.commit()
        return jsonify({"error": "Số điện thoại hoặc mật khẩu không chính xác."}), 401
    if not user.is_active:
        return jsonify({"error": "Tài khoản đã bị khóa."}), 403
    login_user(user)
    return jsonify({"message": "Đăng nhập thành công."}), 200


@bp.route("/api/auth/logout", methods=["POST"])
def api_logout():
    logout_user()
    return jsonify({"message": "Đăng xuất thành công."}), 200


@bp.route("/api/auth/forgot-password", methods=["POST"])
def api_forgot_password():
    return forgot_password()


@bp.route("/api/auth/verify-otp", methods=["POST"])
def api_verify_otp():
    return verify_otp()


@bp.route("/api/auth/reset-password", methods=["POST"])
def api_reset_password():
    return reset_password()
