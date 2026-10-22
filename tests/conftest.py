"""Fixture dùng chung. Test dùng DB riêng (SQLite in-memory mặc định, hoặc TEST_DATABASE_URL),
tuyệt đối không chạm vào database bán hàng thật."""
import re
import shutil

import pytest
from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models import Address, Brand, Category, Product, ProductVariant, User
from config import TestingConfig

PASSWORD = "Passw0rd1"


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
    shutil.rmtree(app.config["UPLOAD_FOLDER"], ignore_errors=True)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def csrf_app():
    cfg = type("CsrfConfig", (TestingConfig,), {"CSRF_ENABLED": True})
    app = create_app(cfg)
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def make_user(app, email="user@example.com", role="CUSTOMER", full_name="Nguyen Van A", active=True,
              password=PASSWORD):
    with app.app_context():
        u = User(full_name=full_name, email=email, role=role, is_active=active, phone="0912345678")
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u.id


def make_address(app, user_id):
    with app.app_context():
        a = Address(user_id=user_id, recipient_name="Nguyen Van A", phone="0912345678", province="TP.HCM",
                    district="Quan 1", ward="Ben Nghe", address_detail="1 Le Loi", is_default=True)
        db.session.add(a)
        db.session.commit()
        return a.id


def make_product(app, code="P-1", price=500000, stock=5, sale_price=None, active=True, sizes=("40",),
                 name=None, category_slug="giay-nam", brand_slug="tuan"):
    """Trả về dict(id, slug, variants=[id...])."""
    with app.app_context():
        cat = db.session.scalar(select(Category).where(Category.slug == category_slug))
        if cat is None:
            cat = Category(name=category_slug, slug=category_slug)
            db.session.add(cat)
        brand = db.session.scalar(select(Brand).where(Brand.slug == brand_slug))
        if brand is None:
            brand = Brand(name=brand_slug.upper(), slug=brand_slug)
            db.session.add(brand)
        db.session.flush()
        p = Product(category_id=cat.id, brand_id=brand.id, name=name or f"Giay {code}", slug=f"giay-{code}".lower(),
                    product_code=code, price=price, sale_price=sale_price, is_active=active)
        db.session.add(p)
        db.session.flush()
        variants = []
        for s in sizes:
            v = ProductVariant(product_id=p.id, size=s, color="", sku=f"{code}-{s}", stock_quantity=stock)
            db.session.add(v)
            variants.append(v)
        db.session.commit()
        return {"id": p.id, "slug": p.slug, "variants": [v.id for v in variants]}


def login(client, email="user@example.com", password=PASSWORD, **kw):
    return client.post("/login", data={"email": email, "password": password}, **kw)


def get_stock(app, variant_id):
    with app.app_context():
        return db.session.get(ProductVariant, variant_id).stock_quantity


def csrf_from(html):
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1) if m else None
