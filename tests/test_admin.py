import io

from sqlalchemy import select

from app.extensions import db
from app.models import Order, Product, ProductImage, ProductVariant
from tests.conftest import get_stock, login, make_address, make_product, make_user

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def admin_client(app):
    make_user(app, email="admin@example.com", role="ADMIN", full_name="Admin")
    c = app.test_client()
    login(c, email="admin@example.com")
    return c


def place_order(app, client_, stock=5, qty=1):
    uid = make_user(app, email="buyer@example.com")
    addr = make_address(app, uid)
    buyer = app.test_client()
    login(buyer, email="buyer@example.com")
    p = make_product(app, stock=stock, price=500000)
    buyer.post("/cart/add", data={"variant_id": p["variants"][0], "quantity": qty})
    buyer.post("/checkout", data={"address_id": addr, "payment_method": "COD"})
    with app.app_context():
        return db.session.scalar(select(Order)).order_code, p


def test_admin_dashboard_and_lists(app):
    c = admin_client(app)
    for url in ["/admin/", "/admin/products", "/admin/categories", "/admin/brands", "/admin/orders",
                "/admin/customers", "/admin/blog", "/admin/contacts", "/admin/products/new", "/admin/blog/new"]:
        assert c.get(url).status_code == 200, url


def test_admin_product_crud_with_validation(app):
    c = admin_client(app)
    p0 = make_product(app, code="SEED-1")  
    with app.app_context():
        from app.models import Brand, Category
        cat_id, brand_id = db.session.scalar(select(Category.id)), db.session.scalar(select(Brand.id))
    form = {"name": "Giày mới", "product_code": "new-1", "price": "750000", "category_id": cat_id,
            "brand_id": brand_id, "is_active": "1", "material": "Da bò", "origin": "Việt Nam"}
    r = c.post("/admin/products/new", data=form)
    assert r.status_code == 302
    with app.app_context():
        p = db.session.scalar(select(Product).where(Product.product_code == "NEW-1"))
        assert p is not None and p.price == 750000 and p.slug == "giay-moi"
        pid = p.id
    # dữ liệu không hợp lệ
    for bad in ({**form, "product_code": "NEW-2", "price": "-5"}, {**form, "product_code": "NEW-3", "price": "abc"},
                {**form, "product_code": "NEW-4", "sale_price": "900000"}, {**form, "product_code": "SEED-1"},
                {**form, "product_code": "NEW-5", "category_id": "9999"}):
        c.post("/admin/products/new", data=bad)
    with app.app_context():
        assert db.session.query(Product).count() == 2  # SEED-1 + NEW-1
    c.post(f"/admin/products/{pid}/edit", data={**form, "name": "Giày đổi tên", "price": "800000"})
    with app.app_context():
        assert db.session.get(Product, pid).name == "Giày đổi tên"
    c.post(f"/admin/products/{pid}/variants", data={"size": "41", "color": "Đen", "stock_quantity": "7"})
    c.post(f"/admin/products/{pid}/variants", data={"size": "41", "color": "Đen", "stock_quantity": "7"}) 
    c.post(f"/admin/products/{pid}/variants", data={"size": "42", "stock_quantity": "-1"})  
    with app.app_context():
        assert db.session.query(ProductVariant).filter_by(product_id=pid).count() == 1
        vid = db.session.scalar(select(ProductVariant.id).where(ProductVariant.product_id == pid))
    c.post(f"/admin/variants/{vid}/update", data={"stock_quantity": "12"})
    assert get_stock(app, vid) == 12
    c.post(f"/admin/variants/{vid}/update", data={"stock_quantity": "-3"})
    assert get_stock(app, vid) == 12
    c.post(f"/admin/products/{pid}/delete")
    with app.app_context():
        assert db.session.get(Product, pid) is None
        assert db.session.get(Product, p0["id"]) is not None


def test_admin_delete_product_with_orders_only_hides_it(app):
    c = admin_client(app)
    _, p = place_order(app, c)
    c.post(f"/admin/products/{p['id']}/delete")
    with app.app_context():
        prod = db.session.get(Product, p["id"])
        assert prod is not None and prod.is_active is False
        assert db.session.query(Order).count() == 1


def test_image_upload_validation(app):
    c = admin_client(app)
    p = make_product(app)
    url = f"/admin/products/{p['id']}/images"
    c.post(url, data={"image": (io.BytesIO(b"<?php echo 1; ?>"), "shell.php")}, content_type="multipart/form-data")
    c.post(url, data={"image": (io.BytesIO(b"not really an image"), "fake.jpg")}, content_type="multipart/form-data")
    with app.app_context():
        assert db.session.query(ProductImage).count() == 0
    c.post(url, data={"image": (io.BytesIO(PNG), "ok.png")}, content_type="multipart/form-data")
    with app.app_context():
        imgs = db.session.scalars(select(ProductImage)).all()
        assert len(imgs) == 1 and imgs[0].is_primary and imgs[0].image_url.startswith("uploads/products/")
        assert imgs[0].image_url.endswith(".png") and "ok" not in imgs[0].image_url  # tên file ngẫu nhiên


def test_admin_order_status_flow_and_stock_restore(app):
    c = admin_client(app)
    code, p = place_order(app, c, stock=5, qty=2)
    v = p["variants"][0]
    assert get_stock(app, v) == 3
    assert c.get(f"/admin/orders/{code}").status_code == 200
    c.post(f"/admin/orders/{code}/status", data={"status": "COMPLETED"})  # nhảy cóc: bị chặn
    with app.app_context():
        assert db.session.scalar(select(Order)).order_status == "PENDING"
    for st in ("CONFIRMED", "SHIPPING", "COMPLETED"):
        c.post(f"/admin/orders/{code}/status", data={"status": st})
    with app.app_context():
        assert db.session.scalar(select(Order)).order_status == "COMPLETED"
    c.post(f"/admin/orders/{code}/status", data={"status": "CANCELLED"})  # trạng thái cuối
    with app.app_context():
        assert db.session.scalar(select(Order)).order_status == "COMPLETED"
    assert get_stock(app, v) == 3


def test_admin_cancel_restores_stock(app):
    c = admin_client(app)
    code, p = place_order(app, c, stock=5, qty=2)
    c.post(f"/admin/orders/{code}/status", data={"status": "CANCELLED"})
    assert get_stock(app, p["variants"][0]) == 5


def test_payment_requires_verification_and_valid_stage(app):
    c = admin_client(app)
    code, _ = place_order(app, c)
    c.post(f"/admin/orders/{code}/payment", data={"payment_status": "PAID", "verification_note": "x"})
    with app.app_context():
        assert db.session.scalar(select(Order)).payment_status == "UNPAID"  # đơn chưa giao
    for st in ("CONFIRMED", "SHIPPING"):
        c.post(f"/admin/orders/{code}/status", data={"status": st})
    c.post(f"/admin/orders/{code}/payment", data={"payment_status": "PAID", "verification_note": ""})
    with app.app_context():
        assert db.session.scalar(select(Order)).payment_status == "UNPAID"  # thiếu ghi chú xác minh
    c.post(f"/admin/orders/{code}/payment", data={"payment_status": "PAID", "verification_note": "NV giao hàng đã thu tiền"})
    with app.app_context():
        o = db.session.scalar(select(Order))
        assert o.payment_status == "PAID" and o.payments[-1].paid_at is not None
        assert o.payments[-1].transaction_code is None
    c.post(f"/admin/orders/{code}/payment", data={"payment_status": "BOGUS", "verification_note": "x"})
    with app.app_context():
        assert db.session.scalar(select(Order)).payment_status == "PAID"


def test_paid_order_cannot_be_cancelled_without_refund(app):
    c = admin_client(app)
    code, p = place_order(app, c, qty=1)
    for st in ("CONFIRMED", "SHIPPING"):
        c.post(f"/admin/orders/{code}/status", data={"status": st})
    c.post(f"/admin/orders/{code}/payment", data={"payment_status": "PAID", "verification_note": "da thu"})
    with app.app_context():
        from app.models import Order as O
        from app.services import order_service
        from app.services import BusinessError
        import pytest
        o = db.session.scalar(select(O))
        o.order_status = "CONFIRMED"
        db.session.commit()
        with pytest.raises(BusinessError):
            order_service.admin_update_status(o, "CANCELLED")


def test_customer_cannot_call_admin_actions(app):
    code, p = place_order(app, None)
    buyer = app.test_client()
    login(buyer, email="buyer@example.com")
    assert buyer.post(f"/admin/orders/{code}/status", data={"status": "CONFIRMED"}).status_code == 403
    assert buyer.post(f"/admin/orders/{code}/payment", data={"payment_status": "PAID", "verification_note": "x"}).status_code == 403
    assert buyer.post(f"/admin/products/{p['id']}/delete").status_code == 403
    with app.app_context():
        assert db.session.scalar(select(Order)).order_status == "PENDING"
        assert db.session.get(Product, p["id"]) is not None


def test_admin_category_brand_blog_contact_and_customers(app):
    from app.models import BlogPost, Brand, Category, ContactMessage, User
    c = admin_client(app)
    c.post("/admin/categories/save", data={"name": "Giày nam", "is_active": "1"})
    c.post("/admin/brands/save", data={"name": "TUẤN", "logo": "images/logo-tuan.png"})
    c.post("/admin/brands/save", data={"name": "BAD", "logo": "../../etc/passwd"})
    with app.app_context():
        assert db.session.query(Category).count() == 1 and db.session.query(Brand).count() == 1
        cat_id, brand_id = db.session.scalar(select(Category.id)), db.session.scalar(select(Brand.id))
    make_product(app, code="IN-USE", category_slug="giay-nam", brand_slug="tuan")
    c.post(f"/admin/categories/{cat_id}/delete")  # đang có sản phẩm trong danh mục "giay-nam" (slug khác tên)
    c.post("/admin/blog/new", data={"title": "Bài mới", "content": "Nội dung bài viết dài đủ.", "status": "PUBLISHED"})
    c.post("/admin/blog/new", data={"title": "x", "content": "ngắn", "status": "PUBLISHED"})
    with app.app_context():
        posts = db.session.scalars(select(BlogPost)).all()
        assert len(posts) == 1 and posts[0].published_at is not None
        db.session.add(ContactMessage(full_name="A B", email="a@b.co", subject="Hello", message="Xin chào shop"))
        db.session.commit()
        mid = db.session.scalar(select(ContactMessage.id))
    c.post(f"/admin/contacts/{mid}/status", data={"status": "RESOLVED"})
    with app.app_context():
        assert db.session.get(ContactMessage, mid).status == "RESOLVED"
    uid = make_user(app, email="cust@example.com")
    c.post(f"/admin/customers/{uid}/toggle")
    with app.app_context():
        assert db.session.get(User, uid).is_active is False
    assert "không đúng" in login(app.test_client(), email="cust@example.com").get_data(as_text=True)
