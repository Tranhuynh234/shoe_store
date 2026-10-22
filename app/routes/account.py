from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.models import Address, Order
from app.models.constants import ORDER_COMPLETED, ORDER_SHIPPING, ORDER_STATUS_LABELS
from app.services import BusinessError, auth_service, dashboard_service, order_service
from app.utils.validators import clean, is_safe_redirect, parse_int

bp = Blueprint("account", __name__, url_prefix="/account")


def _flash_errors(e: BusinessError):
    for msg in (e.args[0] if isinstance(e.args[0], list) else [str(e)]):
        flash(msg, "error")


@bp.route("/")
@login_required
def dashboard():
    return render_template("account/dashboard.html", stats=dashboard_service.customer_stats(current_user),
                           orders=dashboard_service.recent_orders(current_user, 5))


@bp.route("/orders")
@login_required
def orders():
    status = clean(request.args.get("status"), 20).upper() or None
    if status and status not in ORDER_STATUS_LABELS:
        status = None
    page = parse_int(request.args.get("page"), default=1, minimum=1)
    stmt = select(Order).where(Order.user_id == current_user.id)
    if status:
        stmt = stmt.where(Order.order_status == status)
    stmt = stmt.order_by(Order.created_at.desc(), Order.id.desc())
    pagination = db.paginate(stmt, page=page, per_page=10, error_out=False)
    return render_template("account/orders.html", pagination=pagination, orders=pagination.items, status=status,
                           title={"SHIPPING": "Đang giao", "COMPLETED": "Lịch sử mua hàng"}.get(status, "Đơn mua"))


@bp.route("/orders/<order_code>")
@login_required
def order_detail(order_code):
    order = order_service.get_user_order(current_user, order_code)  # chỉ đơn của chính mình
    if order is None:
        abort(404)
    return render_template("account/order_detail.html", order=order)


@bp.route("/orders/<order_code>/cancel", methods=["POST"])
@login_required
def cancel_order(order_code):
    try:
        order_service.cancel_order_by_customer(current_user, order_code)
        flash("Đơn hàng đã được hủy.", "success")
    except BusinessError as e:
        flash(str(e), "error")
    return redirect(url_for("account.order_detail", order_code=order_code))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        try:
            auth_service.update_profile(current_user, request.form.get("full_name"), request.form.get("phone"))
            flash("Đã cập nhật thông tin cá nhân.", "success")
            return redirect(url_for("account.profile"))
        except BusinessError as e:
            _flash_errors(e)
    return render_template("account/profile.html")


@bp.route("/password", methods=["POST"])
@login_required
def password():
    try:
        auth_service.change_password(current_user, request.form.get("current_password"),
                                     request.form.get("new_password"), request.form.get("confirm_password"))
        flash("Đã đổi mật khẩu.", "success")
    except BusinessError as e:
        _flash_errors(e)
    return redirect(url_for("account.profile"))


def _own_address_or_404(address_id):
    address = db.session.get(Address, address_id)
    if address is None or address.user_id != current_user.id:
        abort(404)
    return address


@bp.route("/addresses", methods=["GET", "POST"])
@login_required
def addresses():
    edit = None
    if request.args.get("edit"):
        edit = _own_address_or_404(parse_int(request.args.get("edit"), default=0))
    if request.method == "POST":
        target = _own_address_or_404(parse_int(request.form.get("address_id"), default=0)) \
            if request.form.get("address_id") else None
        try:
            auth_service.save_address(current_user, request.form, target)
            flash("Đã lưu địa chỉ.", "success")
            nxt = request.form.get("next", "")
            return redirect(nxt if is_safe_redirect(nxt) else url_for("account.addresses"))
        except BusinessError as e:
            _flash_errors(e)
            edit = target
    return render_template("account/addresses.html", edit=edit, next=request.args.get("next", ""))


@bp.route("/addresses/<int:address_id>/delete", methods=["POST"])
@login_required
def delete_address(address_id):
    auth_service.delete_address(current_user, _own_address_or_404(address_id))
    flash("Đã xóa địa chỉ.", "success")
    return redirect(url_for("account.addresses"))
