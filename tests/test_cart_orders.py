from sqlalchemy import select

from app.extensions import db
from app.models import CartItem, Order, OrderItem
from tests.conftest import get_stock, login, make_address, make_product, make_user


def add_to_cart(client, variant_id, qty=1, **extra):
    return client.post("/cart/add", data={"variant_id": variant_id, "quantity": qty, **extra}, follow_redirects=True)


def setup_customer(app, client, email="user@example.com"):
    uid = make_user(app, email=email)
    login(client, email=email)
    return uid, make_address(app, uid)


def test_add_to_cart_requires_login(app, client):
    p = make_product(app)
    r = client.post("/cart/add", data={"variant_id": p["variants"][0], "quantity": 1})
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_add_update_remove_cart(app, client):
    setup_customer(app, client)
    p = make_product(app, price=100000, stock=5)
    v = p["variants"][0]
    assert "Đã thêm" in add_to_cart(client, v, 2).get_data(as_text=True)
    add_to_cart(client, v, 1)  # cộng dồn thành 3
    html = client.get("/cart").get_data(as_text=True)
    assert "300.000" in html
    with app.app_context():
        item = db.session.scalar(select(CartItem))
        item_id, qty = item.id, item.quantity
    assert qty == 3
    client.post("/cart/update", data={"item_id": item_id, "quantity": 4})
    with app.app_context():
        assert db.session.get(CartItem, item_id).quantity == 4
    client.post("/cart/remove", data={"item_id": item_id})
    with app.app_context():
        assert db.session.get(CartItem, item_id) is None
    assert "đang trống" in client.get("/cart").get_data(as_text=True)


def test_cannot_add_or_update_beyond_stock(app, client):
    setup_customer(app, client)
    p = make_product(app, stock=2)
    v = p["variants"][0]
    assert "Chỉ còn 2" in add_to_cart(client, v, 3).get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(select(CartItem)) is None
    add_to_cart(client, v, 2)
    with app.app_context():
        item_id = db.session.scalar(select(CartItem)).id
    client.post("/cart/update", data={"item_id": item_id, "quantity": 5})
    with app.app_context():
        assert db.session.get(CartItem, item_id).quantity == 2


def test_invalid_cart_input_rejected(app, client):
    setup_customer(app, client)
    p = make_product(app)
    v = p["variants"][0]
    for qty in ("0", "-1", "abc", "999"):
        add_to_cart(client, v, qty)
    add_to_cart(client, 99999, 1)
    with app.app_context():
        assert db.session.scalar(select(CartItem)) is None


def test_cart_isolated_between_users(app, client):
    setup_customer(app, client)
    p = make_product(app)
    add_to_cart(client, p["variants"][0], 1)
    with app.app_context():
        item_id = db.session.scalar(select(CartItem)).id
    other = app.test_client()
    make_user(app, email="other@example.com")
    login(other, email="other@example.com")
    other.post("/cart/remove", data={"item_id": item_id})
    with app.app_context():
        assert db.session.get(CartItem, item_id) is not None  # người khác không xóa được


def test_checkout_success_creates_order_snapshot_and_clears_cart(app, client):
    uid, addr = setup_customer(app, client)
    p = make_product(app, code="GXHU-A20B", price=810000, stock=5, name="Giày tây nam GXHU-A20B")
    v = p["variants"][0]
    add_to_cart(client, v, 2)
    # Trình duyệt cố gửi giá/tổng tiền giả: server phải bỏ qua
    r = client.post("/checkout", data={"address_id": addr, "payment_method": "COD", "price": "1",
                                       "total_amount": "1", "customer_note": "Giao giờ hành chính"})
    assert r.status_code == 302 and "/order/success/" in r.headers["Location"]
    with app.app_context():
        order = db.session.scalar(select(Order))
        assert order.user_id == uid
        assert order.subtotal == 1620000 and order.shipping_fee == 0  # >= 1.000.000 miễn phí giao hàng
        assert order.total_amount == 1620000
        assert order.order_status == "PENDING" and order.payment_status == "UNPAID"
        assert order.payment_method == "COD" and len(order.payments) == 1
        assert order.payments[0].transaction_code is None  # không tự sinh mã giao dịch
        item = db.session.scalar(select(OrderItem))
        assert (item.product_name, item.product_code, item.unit_price, item.quantity) == \
               ("Giày tây nam GXHU-A20B", "GXHU-A20B", 810000, 2)
        assert order.ship_address.startswith("1 Le Loi")
        assert db.session.scalar(select(CartItem)) is None
    assert get_stock(app, v) == 3
    assert "Đặt hàng thành công" in client.get(r.headers["Location"]).get_data(as_text=True)


def test_shipping_fee_applied_below_threshold(app, client):
    _, addr = setup_customer(app, client)
    p = make_product(app, price=200000)
    add_to_cart(client, p["variants"][0], 1)
    client.post("/checkout", data={"address_id": addr, "payment_method": "COD"})
    with app.app_context():
        o = db.session.scalar(select(Order))
        assert o.shipping_fee == 30000 and o.total_amount == 230000


def test_order_snapshot_survives_price_change(app, client):
    from app.models import Product
    _, addr = setup_customer(app, client)
    p = make_product(app, price=300000)
    add_to_cart(client, p["variants"][0], 1)
    client.post("/checkout", data={"address_id": addr, "payment_method": "COD"})
    with app.app_context():
        db.session.get(Product, p["id"]).price = 999000
        db.session.commit()
        assert db.session.scalar(select(OrderItem)).unit_price == 300000


def test_cannot_oversell_last_item(app, client):
    p = make_product(app, stock=1)
    v = p["variants"][0]
    _, addr1 = setup_customer(app, client, email="one@example.com")
    c2 = app.test_client()
    uid2 = make_user(app, email="two@example.com")
    login(c2, email="two@example.com")
    addr2 = make_address(app, uid2)
    add_to_cart(client, v, 1)
    add_to_cart(c2, v, 1)  # cả hai cùng thấy còn 1 sản phẩm
    assert client.post("/checkout", data={"address_id": addr1, "payment_method": "COD"}).status_code == 302
    r = c2.post("/checkout", data={"address_id": addr2, "payment_method": "COD"}, follow_redirects=True)
    assert "không đủ" in r.get_data(as_text=True) or "tồn kho" in r.get_data(as_text=True)
    with app.app_context():
        assert db.session.query(Order).count() == 1
        assert db.session.scalar(select(CartItem)) is not None  # giỏ của người thua vẫn còn
    assert get_stock(app, v) == 0


def test_failed_order_rolls_back_all_stock_changes(app, client):
    _, addr = setup_customer(app, client)
    a = make_product(app, code="RB-A", stock=5)["variants"][0]
    b = make_product(app, code="RB-B", stock=5)["variants"][0]
    add_to_cart(client, a, 2)
    add_to_cart(client, b, 2)
    with app.app_context():  # có người khác mua mất hàng B trước khi khách thanh toán
        from app.models import ProductVariant
        db.session.get(ProductVariant, b).stock_quantity = 1
        db.session.commit()
    client.post("/checkout", data={"address_id": addr, "payment_method": "COD"})
    with app.app_context():
        assert db.session.query(Order).count() == 0
    assert get_stock(app, a) == 5 and get_stock(app, b) == 1  # kho A không bị trừ dở dang


def test_checkout_rejects_foreign_address_and_empty_cart_and_bad_payment(app, client):
    uid, addr = setup_customer(app, client)
    other_uid = make_user(app, email="x@example.com")
    foreign = make_address(app, other_uid)
    p = make_product(app)
    add_to_cart(client, p["variants"][0], 1)
    client.post("/checkout", data={"address_id": foreign, "payment_method": "COD"})
    client.post("/checkout", data={"address_id": addr, "payment_method": "CARD"})  # chưa hỗ trợ
    with app.app_context():
        assert db.session.query(Order).count() == 0
    client.post("/checkout", data={"address_id": addr, "payment_method": "COD"})
    assert client.get("/checkout").status_code == 302  # giỏ trống sau khi đặt


def test_customer_cannot_view_others_order(app, client):
    _, addr = setup_customer(app, client)
    p = make_product(app)
    add_to_cart(client, p["variants"][0], 1)
    client.post("/checkout", data={"address_id": addr, "payment_method": "COD"})
    with app.app_context():
        code = db.session.scalar(select(Order)).order_code
    assert client.get(f"/account/orders/{code}").status_code == 200
    other = app.test_client()
    make_user(app, email="other@example.com")
    login(other, email="other@example.com")
    assert other.get(f"/account/orders/{code}").status_code == 404
    assert other.get(f"/order/success/{code}").status_code == 404
    other.post(f"/account/orders/{code}/cancel")
    with app.app_context():
        assert db.session.scalar(select(Order)).order_status == "PENDING"


def test_cancel_pending_order_restores_stock_and_blocks_later_cancel(app, client):
    _, addr = setup_customer(app, client)
    p = make_product(app, stock=5)
    v = p["variants"][0]
    add_to_cart(client, v, 2)
    client.post("/checkout", data={"address_id": addr, "payment_method": "COD"})
    assert get_stock(app, v) == 3
    with app.app_context():
        code = db.session.scalar(select(Order)).order_code
    client.post(f"/account/orders/{code}/cancel")
    with app.app_context():
        o = db.session.scalar(select(Order))
        assert o.order_status == "CANCELLED" and o.payment_status == "FAILED"
    assert get_stock(app, v) == 5
    client.post(f"/account/orders/{code}/cancel")  # hủy lần 2 không cộng kho thêm
    assert get_stock(app, v) == 5


def test_cannot_cancel_after_confirmed(app, client):
    _, addr = setup_customer(app, client)
    p = make_product(app, stock=5)
    add_to_cart(client, p["variants"][0], 1)
    client.post("/checkout", data={"address_id": addr, "payment_method": "COD"})
    with app.app_context():
        o = db.session.scalar(select(Order))
        o.order_status, code = "CONFIRMED", o.order_code
        db.session.commit()
    client.post(f"/account/orders/{code}/cancel")
    with app.app_context():
        assert db.session.scalar(select(Order)).order_status == "CONFIRMED"


def test_customer_dashboard_shows_real_counts(app, client):
    uid, addr = setup_customer(app, client)
    html = client.get("/account/").get_data(as_text=True)
    assert "Chưa có dữ liệu hoạt động" in html
    p = make_product(app, stock=20, price=100000)
    for _ in range(4):
        add_to_cart(client, p["variants"][0], 1)
        client.post("/checkout", data={"address_id": addr, "payment_method": "COD"})
    with app.app_context():
        orders = db.session.scalars(select(Order).order_by(Order.id)).all()
        orders[1].order_status = "SHIPPING"
        orders[2].order_status = "COMPLETED"
        orders[3].order_status = "CANCELLED"
        db.session.commit()
    from app.services import dashboard_service
    with app.test_request_context():
        from app.models import User
        stats = dashboard_service.customer_stats(db.session.get(User, uid))
    assert stats == {"total": 4, "processing": 1, "shipping": 1, "completed": 1}
    html = client.get("/account/").get_data(as_text=True)
    assert orders and "Chưa có dữ liệu hoạt động" not in html


def test_address_ownership(app, client):
    uid, addr = setup_customer(app, client)
    other_uid = make_user(app, email="o@example.com")
    foreign = make_address(app, other_uid)
    assert client.get(f"/account/addresses?edit={foreign}").status_code == 404
    assert client.post(f"/account/addresses/{foreign}/delete").status_code == 404
    client.post("/account/addresses", data={
        "recipient_name": "B", "phone": "0911111111", "province": "HN", "district": "Q", "ward": "P",
        "address_detail": "2 Pho Hue", "is_default": "1"})
    with app.app_context():
        from app.models import Address
        assert db.session.query(Address).filter_by(user_id=uid).count() == 2
