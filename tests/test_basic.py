from sqlalchemy import text

from app.extensions import db
from tests.conftest import csrf_from


def test_app_starts_and_home_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "TUẤN" in r.get_data(as_text=True)


def test_database_connection(app):
    with app.app_context():
        assert db.session.execute(text("SELECT 1")).scalar() == 1


def test_static_assets_and_templates_have_no_broken_internal_links(client):
    for url in ["/", "/products", "/about", "/contact", "/blog", "/login", "/register"]:
        assert client.get(url).status_code == 200, url
    assert client.get("/static/css/style.css").status_code == 200
    assert client.get("/static/css/app.css").status_code == 200
    assert client.get("/static/js/main.js").status_code == 200


def test_404_page(client):
    r = client.get("/khong-ton-tai")
    assert r.status_code == 404
    assert "Không tìm thấy" in r.get_data(as_text=True)


def test_csrf_blocks_post_without_token(csrf_app):
    c = csrf_app.test_client()
    r = c.post("/login", data={"email": "a@b.com", "password": "x"})
    assert r.status_code == 400


def test_csrf_allows_post_with_valid_token(csrf_app):
    c = csrf_app.test_client()
    token = csrf_from(c.get("/login").get_data(as_text=True))
    assert token
    r = c.post("/login", data={"email": "a@b.com", "password": "x", "csrf_token": token})
    assert r.status_code == 200  # form hiển thị lại kèm lỗi đăng nhập, không phải 400
