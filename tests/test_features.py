"""Test: sắp xếp/lọc giá, đã xem gần đây, đổi ngôn ngữ, sáng/tối, hover ảnh màu."""
from app.extensions import db
from app.models import ProductImage
from tests.conftest import PASSWORD, login, make_product, make_user


def names_in_order(html, names):
    return sorted(names, key=lambda n: html.index(f"<h3>{n}</h3>"))


def test_sort_by_price_uses_effective_price(app, client):
    make_product(app, code="S-A", name="Alpha", price=300000)
    make_product(app, code="S-B", name="Bravo", price=100000)
    make_product(app, code="S-C", name="Charlie", price=900000, sale_price=200000)  # giá bán thực tế 200.000
    asc = client.get("/products?sort=price_asc").get_data(as_text=True)
    assert names_in_order(asc, ["Alpha", "Bravo", "Charlie"]) == ["Bravo", "Charlie", "Alpha"]
    desc = client.get("/products?sort=price_desc").get_data(as_text=True)
    assert names_in_order(desc, ["Alpha", "Bravo", "Charlie"]) == ["Alpha", "Charlie", "Bravo"]
    assert client.get("/products?sort=hack;drop").status_code == 200  # tham số sort lạ -> mặc định


def test_price_range_filter_and_pagination_keeps_params(app, client):
    make_product(app, code="R-1", name="Cheap", price=100000)
    make_product(app, code="R-2", name="Mid", price=500000)
    make_product(app, code="R-3", name="Pricey", price=2000000)
    html = client.get("/products?min_price=200000&max_price=1000000").get_data(as_text=True)
    assert "<h3>Mid</h3>" in html and "<h3>Cheap</h3>" not in html and "<h3>Pricey</h3>" not in html
    assert client.get("/products?min_price=abc&max_price=-5").status_code == 200
    for i in range(10):
        make_product(app, code=f"PP-{i:02d}", name=f"Pg{i:02d}", price=100000 + i)
    page1 = client.get("/products?sort=price_asc&min_price=1").get_data(as_text=True)
    assert "sort=price_asc" in page1 and "min_price=1" in page1 and "page=2" in page1


def test_recently_viewed_flow(app, client):
    a = make_product(app, code="V-A", name="Aaa")
    b = make_product(app, code="V-B", name="Bbb")
    assert "ĐÃ XEM GẦN ĐÂY" not in client.get("/products").get_data(as_text=True)
    client.get(f"/products/{a['slug']}")
    detail_b = client.get(f"/products/{b['slug']}").get_data(as_text=True)
    assert "ĐÃ XEM GẦN ĐÂY" in detail_b and "<h3>Aaa</h3>" in detail_b
    recent_part = detail_b.split("ĐÃ XEM GẦN ĐÂY")[1].split("SẢN PHẨM LIÊN QUAN")[0]
    assert "<h3>Bbb</h3>" not in recent_part  # không liệt kê chính sản phẩm đang xem
    listing = client.get("/products").get_data(as_text=True)
    section = listing.split("ĐÃ XEM GẦN ĐÂY")[1]
    assert section.index("<h3>Bbb</h3>") < section.index("<h3>Aaa</h3>")  # xem sau hiện trước
    client.post("/recent/clear")
    assert "ĐÃ XEM GẦN ĐÂY" not in client.get("/products").get_data(as_text=True)


def test_recently_viewed_skips_deactivated_products(app, client):
    from app.models import Product
    a = make_product(app, code="D-A", name="Gone")
    client.get(f"/products/{a['slug']}")
    with app.app_context():
        db.session.get(Product, a["id"]).is_active = False
        db.session.commit()
    assert "ĐÃ XEM GẦN ĐÂY" not in client.get("/products").get_data(as_text=True)


def test_language_switch(app, client):
    vi = client.get("/products").get_data(as_text=True)
    assert 'lang="vi"' in vi and "ĐĂNG NHẬP" in vi
    r = client.post("/set-language", data={"lang": "en", "next": "/products"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/products")
    en = client.get("/products").get_data(as_text=True)
    assert 'lang="en"' in en and "LOG IN" in en and "SIGN UP" in en and "ĐĂNG NHẬP" not in en
    assert "Newest" in en and "Price: low to high" in en
    en_login = client.get("/login").get_data(as_text=True)
    assert "Remember me" in en_login and "Password" in en_login
    client.post("/set-language", data={"lang": "vi", "next": "/"})
    assert "ĐĂNG NHẬP" in client.get("/products").get_data(as_text=True)


def test_language_switch_chinese(app, client):
    r = client.post("/set-language", data={"lang": "zh", "next": "/products"})
    assert r.status_code == 302
    zh = client.get("/products").get_data(as_text=True)
    assert 'lang="zh"' in zh and "首页" in zh and "产品" in zh and "ĐĂNG NHẬP" not in zh
    assert "Flag_of_China.png" in zh
    zh_login = client.get("/login").get_data(as_text=True)
    assert "密码" in zh_login
    client.post("/set-language", data={"lang": "vi", "next": "/"})
    assert "ĐĂNG NHẬP" in client.get("/products").get_data(as_text=True)


def test_language_switch_rejects_bad_input(app, client):
    r = client.post("/set-language", data={"lang": "fr", "next": "https://evil.example.com/"})
    assert r.status_code == 302 and "evil.example.com" not in r.headers["Location"]
    assert 'lang="vi"' in client.get("/products").get_data(as_text=True)  # ngôn ngữ lạ bị bỏ qua


def test_english_translates_flash_and_keeps_user_content(app, client):
    make_product(app, code="T-1", name="Giày da thật")
    client.post("/set-language", data={"lang": "en", "next": "/"})
    r = client.post("/login", data={"email": "x@y.com", "password": "wrong"})
    assert "Incorrect email or password." in r.get_data(as_text=True)
    assert "Giày da thật" in client.get("/products").get_data(as_text=True)  # tên sản phẩm không dịch


def test_admin_pages_stay_vietnamese(app, client):
    make_user(app, email="admin@example.com", role="ADMIN")
    login(client, email="admin@example.com")
    client.post("/set-language", data={"lang": "en", "next": "/"})
    html = client.get("/admin/").get_data(as_text=True)
    assert "Tổng quan quản trị" in html


def test_theme_and_language_controls_rendered(client):
    html = client.get("/products").get_data(as_text=True)
    assert 'id="themeToggle"' in html and "localStorage.getItem('theme')" in html
    assert 'action="/set-language"' in html


def test_product_card_hover_images(app, client):
    p = make_product(app, code="H-1", name="Hover shoe")
    with app.app_context():
        for i, primary in enumerate((True, False, False)):
            db.session.add(ProductImage(product_id=p["id"], image_url=f"uploads/products/h{i}.jpg",
                                        is_primary=primary, sort_order=i))
        db.session.commit()
    html = client.get("/products").get_data(as_text=True)
    assert "h0.jpg" in html and 'data-hover="/static/uploads/products/h1.jpg"' in html
    assert html.count('class="card-thumb') == 3
    single = make_product(app, code="H-2", name="One image")
    with app.app_context():
        db.session.add(ProductImage(product_id=single["id"], image_url="uploads/products/solo.jpg", is_primary=True))
        db.session.commit()
    html = client.get("/products").get_data(as_text=True)
    assert 'data-hover="/static/uploads/products/solo.jpg"' in html 