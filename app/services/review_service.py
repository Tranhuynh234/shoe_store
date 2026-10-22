from sqlalchemy import select

from app.extensions import db
from app.models import Order, OrderItem, Review
from app.models.constants import ORDER_COMPLETED
from app.services import BusinessError
from app.utils.validators import clean, parse_int


def create_review(user, product, rating, comment):
    """Chỉ cho đánh giá khi khách đã mua và đơn đã hoàn thành; mỗi dòng đơn hàng đánh giá một lần."""
    rating = parse_int(rating, minimum=1, maximum=5)
    if rating is None:
        raise BusinessError("Điểm đánh giá phải từ 1 đến 5.")
    item = db.session.scalar(
        select(OrderItem).join(Order, OrderItem.order_id == Order.id)
        .outerjoin(Review, Review.order_item_id == OrderItem.id)
        .where(Order.user_id == user.id, Order.order_status == ORDER_COMPLETED,
               OrderItem.product_id == product.id, Review.id.is_(None))
        .order_by(OrderItem.id).limit(1))
    if item is None:
        raise BusinessError("Bạn chỉ có thể đánh giá sản phẩm đã mua và nhận hàng thành công.")
    db.session.add(Review(user_id=user.id, product_id=product.id, order_item_id=item.id,
                          rating=rating, comment=clean(comment, 2000) or None))
    db.session.commit()
