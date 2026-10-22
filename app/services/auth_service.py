from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Address, User
from app.models.constants import ROLE_CUSTOMER
from app.services import BusinessError
from app.utils.validators import clean, normalize_phone, valid_phone, validate_password


def get_user_by_phone(phone):
    phone = normalize_phone(clean(phone, 20))
    return db.session.scalar(select(User).where(User.phone == phone))


def register_user(full_name, phone, password, confirm_password) -> User:
    full_name = clean(full_name, 120) or "Khách hàng"
    phone = normalize_phone(clean(phone, 20))
    errors = []
    if not valid_phone(phone):
        errors.append("Số điện thoại Việt Nam không hợp lệ.")
    pw_error = validate_password(password)
    if pw_error:
        errors.append(pw_error)
    if password != confirm_password:
        errors.append("Mật khẩu xác nhận không khớp.")
    if not errors and get_user_by_phone(phone):
        errors.append("Số điện thoại này đã được đăng ký.")
    if errors:
        raise BusinessError(errors)
    user = User(full_name=full_name, phone=phone, role=ROLE_CUSTOMER)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise BusinessError(["Số điện thoại này đã được đăng ký."])
    return user


def authenticate(phone, password):
    user = get_user_by_phone(phone)
    return user if user and user.is_active and user.check_password(password or "") else None


def update_profile(user: User, full_name, phone):
    full_name = clean(full_name, 120)
    phone = normalize_phone(clean(phone, 20))
    errors = []
    if len(full_name) < 2:
        errors.append("Vui lòng nhập họ tên.")
    if not valid_phone(phone):
        errors.append("Số điện thoại không hợp lệ.")
    existing = get_user_by_phone(phone)
    if existing and existing.id != user.id:
        errors.append("Số điện thoại đã được tài khoản khác sử dụng.")
    if errors:
        raise BusinessError(errors)
    user.full_name, user.phone = full_name, phone
    db.session.commit()


def change_password(user: User, current, new, confirm):
    if not user.check_password(current or ""):
        raise BusinessError(["Mật khẩu hiện tại không đúng."])
    err = validate_password(new)
    if err:
        raise BusinessError([err])
    if new != confirm:
        raise BusinessError(["Mật khẩu xác nhận không khớp."])
    user.set_password(new)
    db.session.commit()


def save_address(user: User, data: dict, address=None):
    fields = {k: clean(data.get(k), 255) for k in
              ("recipient_name", "phone", "province", "district", "ward", "address_detail")}
    fields["phone"] = normalize_phone(fields["phone"])
    labels = {"recipient_name": "Tên người nhận", "province": "Tỉnh/Thành phố", "district": "Quận/Huyện",
              "ward": "Phường/Xã", "address_detail": "Địa chỉ chi tiết"}
    errors = [f"{lbl} không được để trống." for k, lbl in labels.items() if not fields[k]]
    if not valid_phone(fields["phone"]):
        errors.append("Số điện thoại người nhận không hợp lệ.")
    if errors:
        raise BusinessError(errors)
    if address is None:
        address = Address(user_id=user.id)
        db.session.add(address)
    for k, v in fields.items():
        setattr(address, k, v)
    if bool(data.get("is_default")) or not user.addresses:
        for a in user.addresses:
            a.is_default = False
        address.is_default = True
    db.session.commit()
    return address


def delete_address(user: User, address):
    was_default = address.is_default
    db.session.delete(address)
    db.session.flush()
    if was_default:
        remaining = db.session.scalars(select(Address).where(Address.user_id == user.id).order_by(Address.id)).first()
        if remaining:
            remaining.is_default = True
    db.session.commit()
