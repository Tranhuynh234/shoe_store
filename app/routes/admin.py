"""ADMIN"""
import re

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import (BlogPost, Brand, Category, ContactMessage, Order, OrderItem, Product, ProductImage,
                        ProductVariant, User)
from app.models.base import utcnow
from app.models.constants import (CONTACT_STATUSES, CONTACT_STATUS_LABELS, ORDER_STATUSES, ORDER_STATUS_LABELS,
                                  ORDER_TRANSITIONS, PAYMENT_STATUS_LABELS, POST_PUBLISHED, POST_STATUSES,
                                  ROLE_CUSTOMER)
from app.services import BusinessError, dashboard_service, order_service
from app.utils.blog_markup import parse_blog
from app.utils.security import admin_required
from app.utils.uploads import UploadError, delete_uploaded_image, save_blog_image, save_product_image
from app.utils.validators import clean, parse_int, slugify

bp = Blueprint("admin", __name__, url_prefix="/admin")

LOGO_RE = re.compile(r"^(images|uploads)/[A-Za-z0-9_\-./']+$")


@bp.before_request
@admin_required
def _guard():
    """Chốt chặn chung cho toàn blueprint."""
    return None


def _unique_slug(model, base, exclude_id=None):
    slug, n = base, 2
    while True:
        stmt = select(model.id).where(model.slug == slug)
        if exclude_id:
            stmt = stmt.where(model.id != exclude_id)
        if db.session.scalar(stmt) is None:
            return slug
        slug, n = f"{base}-{n}", n + 1


def _page():
    return parse_int(request.args.get("page"), default=1, minimum=1)


def _get_or_404(model, pk):
    obj = db.session.get(model, pk)
    if obj is None:
        abort(404)
    return obj


@bp.route("/")
def dashboard():
    recent = db.session.scalars(select(Order).order_by(Order.created_at.desc()).limit(8)).all()
    return render_template("admin/dashboard.html", stats=dashboard_service.admin_stats(), orders=recent)


# Sản phẩm
def _product_form_errors(product, form):
    errors = []
    name = clean(form.get("name"), 200)
    code = clean(form.get("product_code"), 50).upper()
    price = parse_int(form.get("price"), minimum=0)
    sale_raw = clean(form.get("sale_price"))
    sale = parse_int(sale_raw, minimum=0) if sale_raw else None
    category_id = parse_int(form.get("category_id"))
    brand_id = parse_int(form.get("brand_id")) if form.get("brand_id") else None
    if len(name) < 2:
        errors.append("Tên sản phẩm không được để trống.")
    if not code:
        errors.append("Mã sản phẩm không được để trống.")
    if price is None:
        errors.append("Giá phải là số nguyên không âm.")
    if sale_raw and sale is None:
        errors.append("Giá khuyến mãi không hợp lệ.")
    if price is not None and sale is not None and sale > price:
        errors.append("Giá khuyến mãi không được lớn hơn giá gốc.")
    if db.session.get(Category, category_id or 0) is None:
        errors.append("Vui lòng chọn danh mục.")
    if brand_id and db.session.get(Brand, brand_id) is None:
        errors.append("Thương hiệu không hợp lệ.")
    dup = select(Product.id).where(Product.product_code == code)
    if product.id:
        dup = dup.where(Product.id != product.id)
    if code and db.session.scalar(dup):
        errors.append("Mã sản phẩm đã tồn tại.")
    if errors:
        return errors
    product.name, product.product_code = name, code
    product.slug = _unique_slug(Product, slugify(clean(form.get("slug"), 200) or name), product.id)
    product.price, product.sale_price = price, sale
    product.category_id, product.brand_id = category_id, brand_id
    product.description = clean(form.get("description"), 10000) or None
    product.material = clean(form.get("material"), 255) or None
    product.origin = clean(form.get("origin"), 100) or None
    product.is_active = bool(form.get("is_active"))
    return []


def _product_form_context(product):
    return dict(product=product, categories=db.session.scalars(select(Category).order_by(Category.name)).all(),
                brands=db.session.scalars(select(Brand).order_by(Brand.name)).all())


@bp.route("/products")
def products():
    q = clean(request.args.get("q"), 100)
    stmt = select(Product).options(selectinload(Product.variants), selectinload(Product.category),
                                   selectinload(Product.brand), selectinload(Product.images))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Product.name.like(like), Product.product_code.like(like)))
    pagination = db.paginate(stmt.order_by(Product.id.desc()), page=_page(),
                             per_page=current_app.config["ADMIN_PER_PAGE"], error_out=False)
    return render_template("admin/products.html", pagination=pagination, products=pagination.items, q=q)


@bp.route("/products/new", methods=["GET", "POST"])
def product_new():
    product = Product(is_active=True)
    if request.method == "POST":
        errors = _product_form_errors(product, request.form)
        if errors:
            [flash(e, "error") for e in errors]
        else:
            db.session.add(product)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Không lưu được: mã hoặc đường dẫn sản phẩm bị trùng.", "error")
            else:
                flash("Đã tạo sản phẩm. Hãy thêm kích cỡ/tồn kho và hình ảnh.", "success")
                return redirect(url_for("admin.product_edit", product_id=product.id))
    return render_template("admin/product_form.html", **_product_form_context(product))


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def product_edit(product_id):
    product = _get_or_404(Product, product_id)
    if request.method == "POST":
        errors = _product_form_errors(product, request.form)
        if errors:
            db.session.rollback()
            [flash(e, "error") for e in errors]
            product = _get_or_404(Product, product_id)
        else:
            try:
                db.session.commit()
                flash("Đã cập nhật sản phẩm.", "success")
                return redirect(url_for("admin.product_edit", product_id=product.id))
            except IntegrityError:
                db.session.rollback()
                flash("Không lưu được: mã hoặc đường dẫn sản phẩm bị trùng.", "error")
                product = _get_or_404(Product, product_id)
    return render_template("admin/product_form.html", **_product_form_context(product))


@bp.route("/products/<int:product_id>/delete", methods=["POST"])
def product_delete(product_id):
    product = _get_or_404(Product, product_id)
    has_orders = db.session.scalar(select(func.count(OrderItem.id)).where(OrderItem.product_id == product.id))
    if has_orders:
        product.is_active = False
        db.session.commit()
        flash("Sản phẩm đã có trong đơn hàng nên không xóa hẳn để bảo toàn lịch sử. Đã chuyển sang ẩn.", "warning")
    else:
        files = [i.image_url for i in product.images]
        db.session.delete(product)
        db.session.commit()
        for f in files:
            delete_uploaded_image(f)
        flash("Đã xóa sản phẩm.", "success")
    return redirect(url_for("admin.products"))


@bp.route("/products/<int:product_id>/images", methods=["POST"])
def image_upload(product_id):
    product = _get_or_404(Product, product_id)
    try:
        path = save_product_image(request.files.get("image"))
    except UploadError as e:
        flash(str(e), "error")
    else:
        db.session.add(ProductImage(product_id=product.id, image_url=path, is_primary=not product.images,
                                    sort_order=len(product.images)))
        db.session.commit()
        flash("Đã tải ảnh lên.", "success")
    return redirect(url_for("admin.product_edit", product_id=product.id))


@bp.route("/images/<int:image_id>/primary", methods=["POST"])
def image_primary(image_id):
    img = _get_or_404(ProductImage, image_id)
    for other in img.product.images:
        other.is_primary = other.id == img.id
    db.session.commit()
    flash("Đã đặt làm ảnh chính.", "success")
    return redirect(url_for("admin.product_edit", product_id=img.product_id))


@bp.route("/images/<int:image_id>/delete", methods=["POST"])
def image_delete(image_id):
    img = _get_or_404(ProductImage, image_id)
    product_id, path, was_primary = img.product_id, img.image_url, img.is_primary
    db.session.delete(img)
    db.session.flush()
    if was_primary:
        nxt = db.session.scalars(select(ProductImage).where(ProductImage.product_id == product_id)
                                 .order_by(ProductImage.sort_order, ProductImage.id)).first()
        if nxt:
            nxt.is_primary = True
    db.session.commit()
    delete_uploaded_image(path)
    flash("Đã xóa ảnh.", "success")
    return redirect(url_for("admin.product_edit", product_id=product_id))


@bp.route("/products/<int:product_id>/variants", methods=["POST"])
def variant_add(product_id):
    product = _get_or_404(Product, product_id)
    size, color = clean(request.form.get("size"), 20), clean(request.form.get("color"), 50)
    stock = parse_int(request.form.get("stock_quantity"), minimum=0)
    if not size or stock is None:
        flash("Cần nhập kích cỡ và tồn kho (số nguyên không âm).", "error")
    else:
        sku = clean(request.form.get("sku"), 80) or f"{product.product_code}-{size}" + (f"-{slugify(color).upper()}" if color else "")
        db.session.add(ProductVariant(product_id=product.id, size=size, color=color, sku=sku.upper(),
                                      stock_quantity=stock))
        try:
            db.session.commit()
            flash("Đã thêm biến thể.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Biến thể (kích cỡ/màu) hoặc SKU đã tồn tại.", "error")
    return redirect(url_for("admin.product_edit", product_id=product.id))


@bp.route("/variants/<int:variant_id>/update", methods=["POST"])
def variant_update(variant_id):
    v = _get_or_404(ProductVariant, variant_id)
    stock = parse_int(request.form.get("stock_quantity"), minimum=0)
    if stock is None:
        flash("Tồn kho phải là số nguyên không âm.", "error")
    else:
        v.stock_quantity = stock
        db.session.commit()
        flash("Đã cập nhật tồn kho.", "success")
    return redirect(url_for("admin.product_edit", product_id=v.product_id))


@bp.route("/variants/<int:variant_id>/delete", methods=["POST"])
def variant_delete(variant_id):
    v = _get_or_404(ProductVariant, variant_id)
    pid = v.product_id
    db.session.delete(v)
    db.session.commit()
    flash("Đã xóa biến thể.", "success")
    return redirect(url_for("admin.product_edit", product_id=pid))


# ------------------------------------------------- Danh mục & Thương hiệu
def _simple_list(model, template, endpoint_key):
    items = db.session.scalars(select(model).order_by(model.id)).all()
    counts = dict(db.session.execute(
        select(Product.category_id if model is Category else Product.brand_id, func.count(Product.id))
        .group_by(Product.category_id if model is Category else Product.brand_id)).all())
    edit = _get_or_404(model, parse_int(request.args.get("edit"), default=0)) if request.args.get("edit") else None
    return render_template(template, items=items, counts=counts, edit=edit)


def _simple_save(model, label, list_endpoint, is_brand):
    obj_id = parse_int(request.form.get("id"))
    obj = _get_or_404(model, obj_id) if obj_id else model()
    name = clean(request.form.get("name"), 100)
    if len(name) < 2:
        flash(f"Tên {label} không được để trống.", "error")
        return redirect(url_for(list_endpoint))
    obj.name = name
    obj.slug = _unique_slug(model, slugify(clean(request.form.get("slug"), 120) or name), obj.id)
    obj.description = clean(request.form.get("description"), 2000) or None
    if is_brand:
        logo = clean(request.form.get("logo"), 255)
        if logo and (not LOGO_RE.match(logo) or ".." in logo):
            flash("Đường dẫn logo không hợp lệ (ví dụ: images/logo-tuan.png).", "error")
            return redirect(url_for(list_endpoint))
        obj.logo = logo or None
        cover = clean(request.form.get("cover_image"), 255)
        if cover and (not LOGO_RE.match(cover) or ".." in cover):
            flash("Đường dẫn ảnh đại diện không hợp lệ (ví dụ: images/kodoss.jpg).", "error")
            return redirect(url_for(list_endpoint))
        obj.cover_image = cover or None
    else:
        obj.is_active = bool(request.form.get("is_active"))
    if not obj.id:
        db.session.add(obj)
    try:
        db.session.commit()
        flash(f"Đã lưu {label}.", "success")
    except IntegrityError:
        db.session.rollback()
        flash(f"Tên hoặc đường dẫn {label} đã tồn tại.", "error")
    return redirect(url_for(list_endpoint))


def _simple_delete(model, obj_id, label, list_endpoint):
    obj = _get_or_404(model, obj_id)
    if obj.products:
        flash(f"Không thể xóa {label} đang có sản phẩm. Hãy chuyển hoặc xóa sản phẩm trước.", "error")
    else:
        db.session.delete(obj)
        db.session.commit()
        flash(f"Đã xóa {label}.", "success")
    return redirect(url_for(list_endpoint))


@bp.route("/categories")
def categories():
    return _simple_list(Category, "admin/categories.html", "category")


@bp.route("/categories/save", methods=["POST"])
def category_save():
    return _simple_save(Category, "danh mục", "admin.categories", False)


@bp.route("/categories/<int:obj_id>/delete", methods=["POST"])
def category_delete(obj_id):
    return _simple_delete(Category, obj_id, "danh mục", "admin.categories")


@bp.route("/brands")
def brands():
    return _simple_list(Brand, "admin/brands.html", "brand")


@bp.route("/brands/save", methods=["POST"])
def brand_save():
    return _simple_save(Brand, "thương hiệu", "admin.brands", True)


@bp.route("/brands/<int:obj_id>/delete", methods=["POST"])
def brand_delete(obj_id):
    return _simple_delete(Brand, obj_id, "thương hiệu", "admin.brands")


# ---------------------------------------------------------------- Khách hàng
@bp.route("/customers")
def customers():
    q = clean(request.args.get("q"), 100)
    stmt = select(User).where(User.role == ROLE_CUSTOMER)
    if q:
        stmt = stmt.where(or_(User.email.like(f"%{q}%"), User.full_name.like(f"%{q}%")))
    pagination = db.paginate(stmt.order_by(User.id.desc()), page=_page(),
                             per_page=current_app.config["ADMIN_PER_PAGE"], error_out=False)
    order_counts = dict(db.session.execute(select(Order.user_id, func.count(Order.id)).group_by(Order.user_id)).all())
    return render_template("admin/customers.html", pagination=pagination, customers=pagination.items,
                           order_counts=order_counts, q=q)


@bp.route("/customers/<int:user_id>/toggle", methods=["POST"])
def customer_toggle(user_id):
    user = _get_or_404(User, user_id)
    if user.id == current_user.id or user.role != ROLE_CUSTOMER:
        flash("Không thể khóa tài khoản này.", "error")
    else:
        user.is_active = not user.is_active
        db.session.commit()
        flash("Đã mở khóa tài khoản." if user.is_active else "Đã khóa tài khoản.", "success")
    return redirect(request.referrer or url_for("admin.customers"))


# ------------------------------------------------------------------ Đơn hàng
@bp.route("/orders")
def orders():
    status = clean(request.args.get("status"), 20).upper()
    q = clean(request.args.get("q"), 50)
    stmt = select(Order).options(selectinload(Order.user))
    if status in ORDER_STATUSES:
        stmt = stmt.where(Order.order_status == status)
    else:
        status = ""
    if q:
        stmt = stmt.where(or_(Order.order_code.like(f"%{q}%"), Order.ship_name.like(f"%{q}%"),
                              Order.ship_phone.like(f"%{q}%")))
    pagination = db.paginate(stmt.order_by(Order.created_at.desc(), Order.id.desc()), page=_page(),
                             per_page=current_app.config["ADMIN_PER_PAGE"], error_out=False)
    return render_template("admin/orders.html", pagination=pagination, orders=pagination.items, status=status, q=q)


def _order_or_404(code):
    order = db.session.scalar(select(Order).where(Order.order_code == code)
                              .options(selectinload(Order.items), selectinload(Order.payments),
                                       selectinload(Order.user)))
    if order is None:
        abort(404)
    return order


@bp.route("/orders/<order_code>")
def order_detail(order_code):
    order = _order_or_404(order_code)
    return render_template("admin/order_detail.html", order=order,
                           next_statuses=ORDER_TRANSITIONS.get(order.order_status, ()),
                           payment_labels=PAYMENT_STATUS_LABELS)


@bp.route("/orders/<order_code>/status", methods=["POST"])
def order_status(order_code):
    order = _order_or_404(order_code)
    try:
        order_service.admin_update_status(order, clean(request.form.get("status"), 20).upper())
        flash("Đã cập nhật trạng thái đơn hàng.", "success")
    except BusinessError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.order_detail", order_code=order_code))


@bp.route("/orders/<order_code>/payment", methods=["POST"])
def order_payment(order_code):
    order = _order_or_404(order_code)
    try:
        order_service.admin_update_payment(order, clean(request.form.get("payment_status"), 20).upper(),
                                           request.form.get("verification_note"),
                                           request.form.get("transaction_code"))
        flash("Đã cập nhật trạng thái thanh toán.", "success")
    except BusinessError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.order_detail", order_code=order_code))


# ---------------------------------------------------------------------- Blog
@bp.route("/blog")
def blog():
    posts = db.session.scalars(select(BlogPost).order_by(BlogPost.created_at.desc())).all()
    return render_template("admin/blog.html", posts=posts)


def _blog_save(post):
    title, content = clean(request.form.get("title"), 200), clean(request.form.get("content"), 100000)
    status = request.form.get("status")
    if len(title) < 3 or len(content) < 10 or status not in POST_STATUSES:
        flash("Cần nhập tiêu đề, nội dung và trạng thái hợp lệ.", "error")
        return False
    post.title, post.content = title, content
    post.slug = _unique_slug(BlogPost, slugify(clean(request.form.get("slug"), 200) or title), post.id)
    post.summary = clean(request.form.get("summary"), 500) or None
    thumb = clean(request.form.get("thumbnail"), 255)
    if thumb and (not LOGO_RE.match(thumb) or ".." in thumb):
        flash("Đường dẫn ảnh đại diện không hợp lệ (ví dụ: images/tuan1.jpg).", "error")
        return False
    post.thumbnail = thumb or None
    post.status = status
    if status == POST_PUBLISHED and not post.published_at:
        post.published_at = utcnow()
    if status != POST_PUBLISHED:
        post.published_at = None
    return True


def _form_sections(post):
    """Các mục để dựng lại form: ưu tiên nội dung admin vừa gửi (khi lưu lỗi), nếu không thì nội dung đã lưu."""
    raw = request.form.get("content") if request.method == "POST" else None
    return parse_blog(raw if raw is not None else (post.content or ""), alternate=False)


@bp.route("/blog/upload-image", methods=["POST"])
def blog_upload_image():
    """Tải 1 ảnh cho bài blog (gọi bằng fetch từ form soạn bài), trả về JSON."""
    try:
        path = save_blog_image(request.files.get("image"))
    except UploadError as e:
        return jsonify(error=str(e)), 400
    return jsonify(path=path, url=url_for("static", filename=path))


@bp.route("/blog/new", methods=["GET", "POST"])
def blog_new():
    post = BlogPost()
    if request.method == "POST" and _blog_save(post):
        db.session.add(post)
        db.session.commit()
        flash("Đã tạo bài viết.", "success")
        return redirect(url_for("admin.blog"))
    return render_template("admin/blog_form.html", post=post, sections=_form_sections(post))


@bp.route("/blog/<int:post_id>/edit", methods=["GET", "POST"])
def blog_edit(post_id):
    post = _get_or_404(BlogPost, post_id)
    if request.method == "POST":
        if _blog_save(post):
            db.session.commit()
            flash("Đã cập nhật bài viết.", "success")
            return redirect(url_for("admin.blog"))
        db.session.rollback()
        post = _get_or_404(BlogPost, post_id)
    return render_template("admin/blog_form.html", post=post, sections=_form_sections(post))


@bp.route("/blog/<int:post_id>/delete", methods=["POST"])
def blog_delete(post_id):
    db.session.delete(_get_or_404(BlogPost, post_id))
    db.session.commit()
    flash("Đã xóa bài viết.", "success")
    return redirect(url_for("admin.blog"))


# ------------------------------------------------------------------- Liên hệ
@bp.route("/contacts")
def contacts():
    status = clean(request.args.get("status"), 20).upper()
    stmt = select(ContactMessage)
    if status in CONTACT_STATUSES:
        stmt = stmt.where(ContactMessage.status == status)
    else:
        status = ""
    pagination = db.paginate(stmt.order_by(ContactMessage.created_at.desc()), page=_page(),
                             per_page=current_app.config["ADMIN_PER_PAGE"], error_out=False)
    return render_template("admin/contacts.html", pagination=pagination, messages=pagination.items, status=status,
                           statuses=CONTACT_STATUS_LABELS)


@bp.route("/contacts/<int:msg_id>/status", methods=["POST"])
def contact_status(msg_id):
    msg = _get_or_404(ContactMessage, msg_id)
    new = clean(request.form.get("status"), 20).upper()
    if new not in CONTACT_STATUSES:
        flash("Trạng thái không hợp lệ.", "error")
    else:
        msg.status = new
        db.session.commit()
        flash("Đã cập nhật trạng thái tin nhắn.", "success")
    return redirect(request.referrer or url_for("admin.contacts"))