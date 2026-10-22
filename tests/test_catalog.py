from datetime import datetime, timedelta

from app.extensions import db
from app.models import BlogPost
from tests.conftest import make_product


def test_product_list_and_detail(app, client):
    p = make_product(app, code="GXHU-A20B", price=810000, name="Giày tây nam GXHU-A20B")
    html = client.get("/products").get_data(as_text=True)
    assert "GXHU-A20B" in html and "810.000" in html
    detail = client.get(f"/products/{p['slug']}")
    assert detail.status_code == 200
    d = detail.get_data(as_text=True)
    assert "810.000" in d and "Chưa có ảnh" in d  # thiếu ảnh -> placeholder
    assert "Còn 5" in d


def test_sale_price_displayed(app, client):
    p = make_product(app, code="S-1", price=1000000, sale_price=800000)
    d = client.get(f"/products/{p['slug']}").get_data(as_text=True)
    assert "800.000" in d and "1.000.000" in d and "-20%" in d


def test_filter_by_category_brand_and_search(app, client):
    make_product(app, code="A-1", category_slug="giay-nam", brand_slug="tuan", name="Alpha")
    make_product(app, code="B-1", category_slug="giay-the-thao", brand_slug="nauts", name="Beta")
    nam = client.get("/products?category=giay-nam").get_data(as_text=True)
    assert "Alpha" in nam and "Beta" not in nam
    brand = client.get("/products?brand=nauts").get_data(as_text=True)
    assert "Beta" in brand and "Alpha" not in brand
    by_code = client.get("/products?q=B-1").get_data(as_text=True)
    assert "Beta" in by_code and "Alpha" not in by_code
    assert "Không tìm thấy sản phẩm" in client.get("/products?q=zzzz").get_data(as_text=True)


def test_pagination(app, client):
    for i in range(11):
        make_product(app, code=f"PG-{i:02d}", name=f"Pagetest {i:02d}")
    page1 = client.get("/products").get_data(as_text=True)
    page2 = client.get("/products?page=2").get_data(as_text=True)
    assert page1.count('class="shop-card"') == 9
    assert page2.count('class="shop-card"') == 2
    assert client.get("/products?page=abc").status_code == 200  # tham số xấu không gây lỗi 500


def test_inactive_product_hidden(app, client):
    p = make_product(app, code="H-1", active=False, name="Hidden")
    assert "Hidden" not in client.get("/products").get_data(as_text=True)
    assert client.get(f"/products/{p['slug']}").status_code == 404


def test_sold_count_only_from_completed_orders(app, client):
    p = make_product(app, code="SC-1")
    assert "Đã bán" not in client.get(f"/products/{p['slug']}").get_data(as_text=True)


def test_blog_only_published(app, client):
    with app.app_context():
        now = datetime.utcnow()
        db.session.add_all([
            BlogPost(title="Public", slug="public", content="Noi dung cong khai.", status="PUBLISHED",
                     published_at=now - timedelta(days=1)),
            BlogPost(title="Draft", slug="draft", content="Noi dung nhap.", status="DRAFT"),
        ])
        db.session.commit()
    listing = client.get("/blog").get_data(as_text=True)
    assert "Public" in listing and "Draft" not in listing
    assert client.get("/blog/public").status_code == 200
    assert client.get("/blog/draft").status_code == 404


def test_blog_content_is_escaped(app, client):
    with app.app_context():
        db.session.add(BlogPost(title="X", slug="x", content="<script>alert(1)</script>", status="PUBLISHED",
                                published_at=datetime.utcnow() - timedelta(minutes=1)))
        db.session.commit()
    html = client.get("/blog/x").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


def test_contact_form_saves_and_validates(app, client):
    from app.models import ContactMessage
    client.post("/contact", data={"full_name": "A", "email": "bad", "subject": "x", "message": "short"})
    with app.app_context():
        assert db.session.query(ContactMessage).count() == 0
    r = client.post("/contact", data={"full_name": "Le Van C", "email": "c@example.com", "phone": "0912345678",
                                      "subject": "Hoi ve giay", "message": "Cho toi hoi ve size giay."},
                    follow_redirects=True)
    assert "đã nhận được" in r.get_data(as_text=True)
    with app.app_context():
        msg = db.session.query(ContactMessage).one()
        assert msg.status == "NEW" and msg.email == "c@example.com"
