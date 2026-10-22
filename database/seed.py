"""Dữ liệu mẫu cho môi trường PHÁT TRIỂN.

Chỉ dùng thông tin có thật trong frontend gốc:
  - 3 thương hiệu (TUẤN, KODOSS, NAUT'S) cùng logo/ảnh có sẵn trong static/images
  - 4 danh mục theo menu gốc (Giày nam, Giày nữ, Giày thể thao, Phụ kiện)
  - 1 sản phẩm: GIÀY TÂY NAM GXHU-A20B, 810.000 ₫ (từ product_detail.html gốc)
KHÔNG tạo đánh giá, đơn hàng, giao dịch hay tài khoản. Tài khoản admin tạo bằng `flask create-admin`.

Giả định: ZIP không chứa size/tồn kho nên seed tạo size 39-43 với tồn kho mẫu (mặc định 10).
Hãy chỉnh lại tồn kho thật trong trang quản trị. Tùy chọn --demo thêm sản phẩm/bài viết ghi rõ [DEMO].

Chạy:  python database/seed.py [--demo] [--stock 10]     hoặc     flask seed [--demo]
"""
import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.extensions import db  # noqa: E402
from app.models import BlogPost, Brand, Category, Product, ProductVariant  # noqa: E402

BRANDS = [
    dict(name="TUẤN",   slug="tuan",   logo="images/logo/logo-tuan.png",   cover_image="images/classic/tuan.jpg", description="Giày Tuấn - Đôi giày của bạn."),
    dict(name="KODOSS", slug="kodoss", logo="images/logo/logo-kodoss.png", cover_image="images/morden/kodoss.jpg", description="KODOSS - Phong cách hiện đại."),
    dict(name="NAUT'S", slug="nauts",  logo="images/logo/logo-nauts.png", cover_image="images/sport/nauts.jpg", description="NAUT'S - Đôi giày thể thao lý tưởng."),
]
CATEGORIES = [
    dict(name="Giày nam", slug="giay-nam"), dict(name="Giày nữ", slug="giay-nu"),
    dict(name="Giày thể thao", slug="giay-the-thao"), dict(name="Phụ kiện", slug="phu-kien"),
]
SIZES = ["39", "40", "41", "42", "43"]


def _get_or_create(model, key, **values):
    obj = db.session.scalar(select(model).filter_by(**key))
    if obj is None:
        obj = model(**key, **values)
        db.session.add(obj)
        db.session.flush()
    return obj


def _product(code, slug, name, category, brand, price, stock, **extra):
    p = db.session.scalar(select(Product).where(Product.product_code == code))
    if p is None:
        p = Product(product_code=code, slug=slug, name=name, category_id=category.id, brand_id=brand.id,
                    price=price, is_active=True, **extra)
        db.session.add(p)
        db.session.flush()
        for size in SIZES:
            db.session.add(ProductVariant(product_id=p.id, size=size, color="", sku=f"{code}-{size}",
                                          stock_quantity=stock))
    return p


def run_seed(demo=False, stock=10):
    brands = {}
    for b in BRANDS:
        obj = _get_or_create(Brand, {"slug": b["slug"]}, **{k: v for k, v in b.items() if k != "slug"})
        obj.logo = b["logo"]               
        obj.cover_image = b["cover_image"]
        brands[b["slug"]] = obj
    cats = {c["slug"]: _get_or_create(Category, {"slug": c["slug"]}, name=c["name"], is_active=True)
            for c in CATEGORIES}

    _product("GXHU-A20B", "giay-tay-nam-gxhu-a20b", "Giày tây nam GXHU-A20B", cats["giay-nam"], brands["tuan"],
             810000, stock, origin="Việt Nam",
             material="Da bò thật 100% nhập khẩu nguyên miếng. Đế cao su đúc nguyên khối.")

    if demo:
        note = "[DEMO] Sản phẩm mẫu để thử giao diện, giá và tồn kho không phải dữ liệu thật."
        _product("DEMO-KDS-001", "demo-kodoss-001", "[DEMO] Giày KODOSS mẫu", cats["giay-nam"], brands["kodoss"],
                 1000000, stock, description=note, origin="Việt Nam")
        _product("DEMO-NAU-001", "demo-nauts-001", "[DEMO] Giày thể thao NAUT'S mẫu", cats["giay-the-thao"],
                 brands["nauts"], 900000, stock, description=note, origin="Việt Nam")
        if db.session.scalar(select(BlogPost).where(BlogPost.slug == "demo-bai-viet-mau")) is None:
            db.session.add(BlogPost(
                title="[DEMO] Bài viết mẫu", slug="demo-bai-viet-mau", summary="Bài viết mẫu để thử giao diện blog.",
                content="Đây là bài viết DEMO. Hãy xóa hoặc thay bằng nội dung thật trong trang quản trị.",
                status="PUBLISHED", published_at=datetime.utcnow()))
    db.session.commit()
    print(f"Seed xong (demo={demo}). Tồn kho mẫu mỗi size = {stock}: hãy cập nhật số thật trong trang quản trị.")
    print("Tạo tài khoản quản trị bằng:  flask create-admin")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--stock", type=int, default=10)
    args = ap.parse_args()
    from app import create_app
    with create_app().app_context():
        run_seed(demo=args.demo, stock=args.stock)
