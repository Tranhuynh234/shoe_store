import logging
import mimetypes
import os
import secrets

import click
from flask import Flask, g, render_template, request, session
from flask_login import current_user
from sqlalchemy import event
from sqlalchemy.engine import Engine

from config import CONFIGS, DevelopmentConfig

from .extensions import db, login_manager, migrate

# Windows đôi khi map sai đuôi video trong registry; kèm header nosniff thì trình duyệt sẽ từ chối phát.
for _ext, _mime in ((".mp4", "video/mp4"), (".webm", "video/webm"), (".mov", "video/quicktime")):
    mimetypes.add_type(_mime, _ext)


@event.listens_for(Engine, "connect")
def _sqlite_enable_fk(dbapi_connection, _record):
    """SQLite mặc định tắt khóa ngoại; bật lên để môi trường test hành xử giống MySQL."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def create_app(config=None):
    app = Flask(__name__)
    if isinstance(config, type):
        cfg = config
    else:
        cfg = CONFIGS.get(config or os.getenv("APP_ENV", "development"), DevelopmentConfig)
    app.config.from_object(cfg)

    if not app.config.get("SECRET_KEY"):
        if app.config.get("DEBUG") or app.config.get("TESTING"):
            app.config["SECRET_KEY"] = secrets.token_hex(32)
            app.logger.warning("SECRET_KEY chưa được đặt: dùng khóa tạm (phiên đăng nhập mất khi khởi động lại).")
        else:
            raise RuntimeError("Thiếu SECRET_KEY. Hãy đặt trong file .env.")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from . import models  # noqa: F401  (đăng ký model cho SQLAlchemy/Migrate)

    from .routes import register_blueprints
    register_blueprints(app)
    _register_hooks(app)
    _register_errors(app)
    _register_cli(app)
    return app


def _register_hooks(app):
    from .models.constants import (CONTACT_STATUS_LABELS, ORDER_STATUS_LABELS, PAYMENT_STATUS_LABELS)
    from .services import cart_service, catalog_service
    from .i18n import DEFAULT_LANG, LANGS, translate_html
    from .utils import formatting
    from .utils.csrf import generate_csrf_token, protect_csrf

    @app.before_request
    def detect_language():
        lang = request.cookies.get("lang", DEFAULT_LANG)
        g.lang = lang if lang in LANGS else DEFAULT_LANG

    app.before_request(protect_csrf)
    app.jinja_env.globals["csrf_token"] = generate_csrf_token  # dùng được cả trong macro
    app.jinja_env.filters.update(vnd=formatting.vnd, paragraphs=formatting.paragraphs, dt=formatting.dt,
                                 order_status=formatting.order_status_label,
                                 payment_status=formatting.payment_status_label,
                                 contact_status=formatting.contact_status_label)

    @app.context_processor
    def inject_globals():
        ctx = {"lang": g.get("lang", DEFAULT_LANG), "ORDER_STATUS_LABELS": ORDER_STATUS_LABELS,
               "PAYMENT_STATUS_LABELS": PAYMENT_STATUS_LABELS, "CONTACT_STATUS_LABELS": CONTACT_STATUS_LABELS,
               "menu_categories": catalog_service.active_categories(),
               "category_tree": catalog_service.CATEGORY_TREE, "cart_count": 0}
        if current_user.is_authenticated and not current_user.is_admin:
            ctx["cart_count"] = cart_service.cart_quantity(current_user)
        elif not current_user.is_authenticated:
            ctx["cart_count"] = sum(max(0, int(item.get("quantity", 0))) for item in session.get("guest_cart", [])
                                   if isinstance(item, dict))
        return ctx

    @app.after_request
    def translate_response(resp):
        """Khi chọn tiếng Anh / Trung: dịch HTML các trang khách hàng (trang admin giữ tiếng Việt)."""
        lang = g.get("lang", DEFAULT_LANG)
        if (lang != DEFAULT_LANG and resp.mimetype == "text/html" and not resp.direct_passthrough
                and request.blueprint != "admin"):
            resp.set_data(translate_html(resp.get_data(as_text=True), lang))
        return resp

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp


def _register_errors(app):
    messages = {
        400: ("Yêu cầu không hợp lệ", "Phiên làm việc không hợp lệ hoặc dữ liệu gửi lên không đúng. Vui lòng tải lại trang."),
        403: ("Không có quyền truy cập", "Bạn không có quyền thực hiện thao tác này."),
        404: ("Không tìm thấy trang", "Trang bạn tìm không tồn tại hoặc đã bị di chuyển."),
        413: ("Tệp quá lớn", "Dung lượng tệp vượt quá giới hạn 5 MB."),
        500: ("Đã xảy ra lỗi", "Hệ thống gặp sự cố. Vui lòng thử lại sau."),
    }

    def make_handler(code):
        def handler(err):
            if code == 500:
                db.session.rollback()
            title, text = messages[code]
            if code == 400 and getattr(err, "description", None) and "Phiên" in str(err.description):
                text = err.description
            return render_template("error.html", code=code, title=title, message=text), code
        return handler

    for code in messages:
        app.register_error_handler(code, make_handler(code))


def _register_cli(app):
    from .models import User
    from .models.constants import ROLE_ADMIN
    from .utils.validators import normalize_phone, valid_phone, validate_password

    @app.cli.command("seed")
    @click.option("--demo", is_flag=True, help="Thêm sản phẩm/bài viết DEMO để thử giao diện.")
    def seed_command(demo):
        from database.seed import run_seed
        run_seed(demo=demo)

    @app.cli.command("sync-categories")
    def sync_categories_command():
        """Thêm các danh mục (giày tây, giày lười, sandal...) còn thiếu vào database."""
        from .services import catalog_service
        created = catalog_service.sync_categories()
        click.echo("Đã thêm: " + ", ".join(created) if created else "Danh mục đã đầy đủ, không có gì để thêm.")

    @app.cli.command("create-admin")
    @click.option("--phone", default=None, help="Số điện thoại quản trị viên.")
    @click.option("--name", default="Quản trị viên")
    @click.option("--password", default=None, help="Nên bỏ trống để nhập ẩn khi chạy lệnh.")
    @click.option("--promote", is_flag=True, help="Nâng quyền cho số điện thoại đã tồn tại.")
    def create_admin(phone, name, password, promote):
        """Tạo hoặc nâng quyền ADMIN bằng số điện thoại."""
        phone = normalize_phone(phone or os.getenv("ADMIN_PHONE") or click.prompt("Số điện thoại admin"))
        if not valid_phone(phone):
            raise click.ClickException("Số điện thoại Việt Nam không hợp lệ.")
        existing = User.query.filter_by(phone=phone).first()
        if existing and not promote:
            raise click.ClickException("Số điện thoại đã tồn tại. Dùng --promote để nâng quyền.")
        if existing:
            existing.role, existing.is_active = ROLE_ADMIN, True
            db.session.commit()
            click.echo(f"Đã nâng quyền ADMIN cho {phone}.")
            return
        password = password or os.getenv("ADMIN_PASSWORD") or click.prompt(
            "Mật khẩu", hide_input=True, confirmation_prompt=True)
        err = validate_password(password)
        if err:
            raise click.ClickException(err)
        user = User(full_name=name, phone=phone, role=ROLE_ADMIN)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Đã tạo ADMIN: {phone}")