from flask import current_app
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Brand, Category, OrderItem, Product, Order, Review
from app.models.constants import ORDER_COMPLETED


# Cây danh mục dùng chung cho menu bên, bộ lọc và lệnh đồng bộ vào database.
CATEGORY_TREE = [
    {"title": "Sản phẩm nam", "slug": "giay-nam", "name": "Giày nam", "suffix": "Nam", "items": [
        ("Giày Kodoss", "giay-kodoss"),
        ("Giày Tây Nam", "giay-tay-nam"),
        ("Giày Lười Nam", "giay-luoi-nam"),
        ("Giày Thể Thao", "giay-the-thao-nam"),
        ("Giày Hè", "giay-he-nam"),
        ("Sandal", "sandal-nam"),
        ("Dép", "dep-nam"),
    ]},
    {"title": "Sản phẩm nữ", "slug": "giay-nu", "name": "Giày nữ", "suffix": "Nữ", "items": [
        ("Giày Magari", "giay-magari"),
        ("Giày Cao Gót", "giay-cao-got"),
        ("Giày Búp Bê", "giay-bup-be"),
        ("Giày Thể Thao", "giay-the-thao-nu"),
        ("Sandal", "sandal-nu"),
        ("Dép", "dep-nu"),
    ]},
    {"title": "Phụ kiện", "slug": "phu-kien", "name": "Phụ kiện", "suffix": "", "items": [
        ("Ví", "vi"),
        ("Thắt Lưng", "that-lung"),
    ]},
]


def expand_category_slugs(slug):
    """Chọn danh mục cha (vd giay-nam) thì lấy luôn các danh mục con."""
    for group in CATEGORY_TREE:
        if slug == group["slug"]:
            return [slug] + [child for _, child in group["items"]]
    return [slug]


def sync_categories():
    """Tạo các danh mục còn thiếu trong database theo CATEGORY_TREE. Trả về danh sách đã tạo."""
    labels = [label for g in CATEGORY_TREE for label, _ in g["items"]]
    created = []
    existing_slugs = set(db.session.scalars(select(Category.slug)).all())
    existing_names = {n.lower() for n in db.session.scalars(select(Category.name)).all()}
    wanted = []
    for g in CATEGORY_TREE:
        wanted.append((g["name"], g["slug"]))
        for label, slug in g["items"]:
            # Tên danh mục là duy nhất nên các mục trùng tên (Sandal, Dép...) được thêm Nam/Nữ phía sau
            name = f"{label} {g['suffix']}".strip() if labels.count(label) > 1 else label
            wanted.append((name, slug))
    for name, slug in wanted:
        if slug in existing_slugs or name.lower() in existing_names:
            continue
        db.session.add(Category(name=name, slug=slug, is_active=True))
        existing_slugs.add(slug)
        existing_names.add(name.lower())
        created.append(f"{name} ({slug})")
    db.session.commit()
    return created


def active_categories():
    return db.session.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.id)).all()


def all_brands():
    return db.session.scalars(select(Brand).order_by(Brand.id)).all()


SORTS = ("newest", "price_asc", "price_desc")


def search_products(category_slug=None, brand_slug=None, q=None, page=1, per_page=None,
                    sort="newest", min_price=None, max_price=None):
    per_page = per_page or current_app.config["PRODUCTS_PER_PAGE"]
    stmt = (select(Product)
            .join(Category, Product.category_id == Category.id)
            .where(Product.is_active.is_(True), Category.is_active.is_(True))
            .options(selectinload(Product.images), selectinload(Product.variants), selectinload(Product.brand)))
    if category_slug:
        stmt = stmt.where(Category.slug.in_(expand_category_slugs(category_slug)))
    if brand_slug:
        stmt = stmt.join(Brand, Product.brand_id == Brand.id).where(Brand.slug == brand_slug)
    if q:
        like = f"%{q.replace('%', '').replace('_', '')}%"
        stmt = stmt.where(or_(Product.name.like(like), Product.product_code.like(like)))
    price = func.coalesce(Product.sale_price, Product.price)  # giá thực tế đang bán
    if min_price is not None:
        stmt = stmt.where(price >= min_price)
    if max_price is not None:
        stmt = stmt.where(price <= max_price)
    if sort == "price_asc":
        stmt = stmt.order_by(price.asc(), Product.id.desc())
    elif sort == "price_desc":
        stmt = stmt.order_by(price.desc(), Product.id.desc())
    else:
        stmt = stmt.order_by(Product.created_at.desc(), Product.id.desc())
    return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


def get_active_product(slug):
    return db.session.scalar(
        select(Product).where(Product.slug == slug, Product.is_active.is_(True))
        .options(selectinload(Product.images), selectinload(Product.variants),
                 selectinload(Product.brand), selectinload(Product.category)))


_NAME_STOPWORDS = {"giay", "va", "cho", "cua", "mau"}


def _name_tokens(name):
    """Tách tên sản phẩm thành các từ không dấu, bỏ từ quá chung (vd 'giày')."""
    from app.utils.validators import slugify
    return {t for t in slugify(name or "").split("-") if len(t) > 1 and t not in _NAME_STOPWORDS}


def _product_tokens(p):
    """Từ trong tên sản phẩm, bỏ tên thương hiệu để chỉ so sánh phần tên mẫu (Loafer, Tây, Thể Thao...)."""
    brand = getattr(p, "brand", None)
    return _name_tokens(p.name) - _name_tokens(getattr(brand, "name", ""))


def rank_by_name(product, candidates, limit=4):
    """Xếp sản phẩm theo độ giống của tên (không tính thương hiệu); từ hiếm dùng chung được điểm cao hơn."""
    import math
    from collections import Counter
    base = _product_tokens(product)
    docs = {c.id: _product_tokens(c) for c in candidates}
    df = Counter(t for toks in docs.values() for t in toks)
    n = len(candidates) + 1
    scored = []
    for c in candidates:
        shared = base & docs[c.id]
        if not shared:
            continue
        score = sum(math.log((n + 1) / (df[t] + 1)) + 1 for t in shared)
        scored.append((score, c.id, c))
    scored.sort(key=lambda x: x[:2], reverse=True)  # điểm cao trước, bằng điểm thì sản phẩm mới hơn trước
    return [x[-1] for x in scored[:limit]]


def related_products(product, limit=10):
    """Đề xuất sản phẩm có tên tương tự (không xét thương hiệu hay danh mục)."""
    candidates = db.session.scalars(
        select(Product).where(Product.is_active.is_(True), Product.id != product.id)
        .options(selectinload(Product.images), selectinload(Product.variants), selectinload(Product.brand))
        .order_by(Product.id.desc())).all()
    return rank_by_name(product, candidates, limit)


def sold_count(product_id) -> int:
    """Số lượng đã bán = tổng số lượng trong các đơn đã hoàn thành (dữ liệu thật)."""
    total = db.session.scalar(
        select(func.coalesce(func.sum(OrderItem.quantity), 0))
        .join(Order, OrderItem.order_id == Order.id)
        .where(OrderItem.product_id == product_id, Order.order_status == ORDER_COMPLETED))
    return int(total or 0)


def rating_summary(product_id):
    avg, count = db.session.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.product_id == product_id)).one()
    return (round(float(avg), 1) if avg else None), int(count)