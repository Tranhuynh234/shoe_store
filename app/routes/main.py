from flask import Blueprint, render_template, redirect, url_for, request, make_response, abort, flash
from flask_login import current_user
from sqlalchemy import select

from app.extensions import db
from app.models import BlogPost, ContactMessage, Order, OrderItem, Review
from app.models.constants import ORDER_COMPLETED, POST_PUBLISHED
from app.models.base import utcnow
from app.i18n import LANGS
from app.services import BusinessError, catalog_service, recent_service, review_service
from app.utils.validators import clean, is_safe_redirect, parse_int, valid_phone, normalize_phone
from app.utils.blog_markup import parse_blog

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    return render_template("index.html", brands=catalog_service.all_brands())


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/portfolio")
def portfolio():
    return render_template("portfolio.html")


@bp.route("/products")
def products():
    category = clean(request.args.get("category"), 120) or None
    brand = clean(request.args.get("brand"), 120) or None
    q = clean(request.args.get("q"), 100) or None
    page = parse_int(request.args.get("page"), default=1, minimum=1)
    sort = request.args.get("sort") if request.args.get("sort") in catalog_service.SORTS else "newest"
    min_price = parse_int(request.args.get("min_price"), minimum=0)
    max_price = parse_int(request.args.get("max_price"), minimum=0)
    pagination = catalog_service.search_products(category, brand, q, page, sort=sort,
                                                   min_price=min_price, max_price=max_price)
    current_category = next((c for c in catalog_service.active_categories() if c.slug == category), None)
    current_brand = next((b for b in catalog_service.all_brands() if b.slug == brand), None)
    return render_template("shop/products.html", pagination=pagination, products=pagination.items,
                           brands=catalog_service.all_brands(), current_category=current_category,
                           current_brand=current_brand, q=q or "", category=category, brand=brand,
                           sort=sort, min_price=min_price, max_price=max_price,
                           recent=recent_service.recently_viewed(limit=6))


@bp.route("/products/<slug>")
def product_detail(slug):
    product = catalog_service.get_active_product(slug)
    if product is None:
        abort(404)
    recent_service.remember(product.id)
    avg, count = catalog_service.rating_summary(product.id)
    reviews = db.session.scalars(select(Review).where(Review.product_id == product.id)
                                 .order_by(Review.created_at.desc()).limit(20)).all()
    can_review = False
    if current_user.is_authenticated:
        can_review = db.session.scalar(
            select(OrderItem.id).join(Order, OrderItem.order_id == Order.id)
            .outerjoin(Review, Review.order_item_id == OrderItem.id)
            .where(Order.user_id == current_user.id, Order.order_status == ORDER_COMPLETED,
                   OrderItem.product_id == product.id, Review.id.is_(None)).limit(1)) is not None
    return render_template("shop/product_detail.html", product=product,
                           related=catalog_service.related_products(product),
                           sold=catalog_service.sold_count(product.id), rating_avg=avg, rating_count=count,
                           reviews=reviews, can_review=can_review,
                           recent=recent_service.recently_viewed(exclude_id=product.id, limit=6))


@bp.route("/products/<slug>/review", methods=["POST"])
def submit_review(slug):
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=url_for("main.product_detail", slug=slug)))
    product = catalog_service.get_active_product(slug)
    if product is None:
        abort(404)
    try:
        review_service.create_review(current_user, product, request.form.get("rating"), request.form.get("comment"))
        flash("Cảm ơn bạn đã đánh giá sản phẩm.", "success")
    except BusinessError as e:
        flash(str(e), "error")
    return redirect(url_for("main.product_detail", slug=slug))


@bp.route("/blog")
def blog_list():
    page = parse_int(request.args.get("page"), default=1, minimum=1)
    stmt = (select(BlogPost).where(BlogPost.status == POST_PUBLISHED, BlogPost.published_at <= utcnow())
            .order_by(BlogPost.published_at.desc()))
    pagination = db.paginate(stmt, page=page, per_page=6, error_out=False)
    return render_template("blog/list.html", pagination=pagination, posts=pagination.items)


@bp.route("/blog/<slug>")
def blog_detail(slug):
    post = db.session.scalar(select(BlogPost).where(BlogPost.slug == slug, BlogPost.status == POST_PUBLISHED,
                                                    BlogPost.published_at <= utcnow()))
    if post is None:
        abort(404)
    return render_template("blog/detail.html", post=post, sections=parse_blog(post.content))


@bp.route("/contact", methods=["GET", "POST"])
def contact():
    form = {}
    if request.method == "POST":
        form = {k: clean(request.form.get(k), 5000 if k == "message" else 200)
                for k in ("full_name", "phone", "subject", "message")}
        form["phone"] = normalize_phone(form["phone"])
        errors = []
        if len(form["full_name"]) < 2:
            errors.append("Vui lòng nhập họ tên.")
        if form["phone"] and not valid_phone(form["phone"]):
            errors.append("Số điện thoại không hợp lệ.")
        if len(form["subject"]) < 3:
            errors.append("Vui lòng nhập tiêu đề (tối thiểu 3 ký tự).")
        if len(form["message"]) < 10:
            errors.append("Nội dung tin nhắn quá ngắn (tối thiểu 10 ký tự).")
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            db.session.add(ContactMessage(full_name=form["full_name"], phone=form["phone"] or "", subject=form["subject"],
                                         message=form["message"]))
            db.session.commit()
            flash("Cảm ơn bạn! Chúng tôi đã nhận được tin nhắn và sẽ phản hồi sớm.", "success")
            return redirect(url_for("main.contact"))
    return render_template("contact.html", form=form)


@bp.route("/recent/clear", methods=["POST"])
def clear_recent():
    recent_service.clear()
    nxt = request.form.get("next", "")
    return redirect(nxt if is_safe_redirect(nxt) else url_for("main.products"))


@bp.route("/set-language", methods=["POST"])
def set_language():
    lang = request.form.get("lang")
    nxt = request.form.get("next", "")
    resp = make_response(redirect(nxt if is_safe_redirect(nxt) else url_for("main.home")))
    if lang in LANGS:
        resp.set_cookie("lang", lang, max_age=365 * 24 * 3600, samesite="Lax", httponly=True,
                        secure=bool(request.is_secure))
    return resp