from sqlalchemy import select

from app.extensions import db
from app.models import User
from tests.conftest import PASSWORD, login, make_user

REG = {"full_name": "Tran Thi B", "email": "b@example.com", "phone": "0987654321",
       "password": PASSWORD, "confirm_password": PASSWORD}


def test_register_success_hashes_password_and_logs_in(app, client):
    r = client.post("/register", data=REG, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        u = db.session.scalar(select(User).where(User.email == "b@example.com"))
        assert u is not None and u.role == "CUSTOMER"
        assert u.password_hash != PASSWORD and PASSWORD not in u.password_hash
    assert client.get("/account/").status_code == 200


def test_register_cannot_set_admin_role(app, client):
    client.post("/register", data={**REG, "role": "ADMIN"})
    with app.app_context():
        assert db.session.scalar(select(User).where(User.email == "b@example.com")).role == "CUSTOMER"


def test_register_rejects_invalid_data(app, client):
    bad = [{**REG, "email": "not-an-email"}, {**REG, "confirm_password": "Different1"},
           {**REG, "password": "short", "confirm_password": "short"},
           {**REG, "password": "onlyletters", "confirm_password": "onlyletters"},
           {**REG, "phone": "123"}, {**REG, "full_name": ""}]
    for data in bad:
        client.post("/register", data=data)
    with app.app_context():
        assert db.session.scalar(select(User).where(User.email == "b@example.com")) is None


def test_register_duplicate_email(app, client):
    make_user(app, email="b@example.com")
    r = client.post("/register", data=REG)
    assert "đã được đăng ký" in r.get_data(as_text=True)
    with app.app_context():
        assert len(db.session.scalars(select(User).where(User.email == "b@example.com")).all()) == 1


def test_login_logout_flow(app, client):
    make_user(app)
    assert "không đúng" in login(client, password="WrongPass1").get_data(as_text=True)
    r = login(client, follow_redirects=True)
    assert r.status_code == 200
    assert client.get("/account/").status_code == 200
    client.post("/logout")
    assert client.get("/account/").status_code == 302  # bị chuyển về trang đăng nhập


def test_inactive_user_cannot_login(app, client):
    make_user(app, active=False)
    login(client)
    assert client.get("/account/").status_code == 302


def test_login_required_redirects_anonymous(client):
    for url in ["/account/", "/cart", "/checkout", "/account/orders", "/account/profile"]:
        r = client.get(url)
        assert r.status_code == 302 and "/login" in r.headers["Location"], url


def test_login_does_not_redirect_to_external_site(app, client):
    make_user(app)
    r = client.post("/login", data={"email": "user@example.com", "password": PASSWORD,
                                    "next": "https://evil.example.com/"})
    assert r.status_code == 302 and "evil.example.com" not in r.headers["Location"]


def test_customer_cannot_access_admin(app, client):
    make_user(app)
    login(client)
    for url in ["/admin/", "/admin/products", "/admin/orders", "/admin/customers"]:
        assert client.get(url).status_code == 403, url
    assert client.post("/admin/products/new", data={"name": "x"}).status_code == 403


def test_anonymous_redirected_from_admin(client):
    assert client.get("/admin/").status_code == 302


def test_profile_update_and_validation(app, client):
    make_user(app)
    login(client)
    client.post("/account/profile", data={"full_name": "Ten Moi", "phone": "0901234567"})
    with app.app_context():
        u = db.session.scalar(select(User).where(User.email == "user@example.com"))
        assert u.full_name == "Ten Moi" and u.phone == "0901234567"
    client.post("/account/profile", data={"full_name": "Ten Khac", "phone": "abc"})
    with app.app_context():
        assert db.session.scalar(select(User).where(User.email == "user@example.com")).full_name == "Ten Moi"


def test_profile_cannot_change_role(app, client):
    make_user(app)
    login(client)
    client.post("/account/profile", data={"full_name": "A B", "phone": "", "role": "ADMIN"})
    with app.app_context():
        assert db.session.scalar(select(User).where(User.email == "user@example.com")).role == "CUSTOMER"
