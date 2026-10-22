# Giày Tuấn – Website thương mại điện tử (Flask + MySQL)

Chuyển từ khung Django rỗng + 3 template HTML sang **Flask / Jinja2 / Flask-SQLAlchemy / MySQL 8**.
Giữ nguyên giao diện gốc (`style.css`, hero, side-menu, brand grid, footer, dashboard, trang chi tiết sản phẩm).

## Tình trạng xác minh (đọc trước)
- **Đã kiểm tra tĩnh:** toàn bộ file Python biên dịch được; 41 template Jinja parse không lỗi; 128 tham chiếu `url_for` đều trỏ tới route tồn tại.
- **CHƯA chạy được** trong môi trường phát triển ra bản này (không có mạng để cài SQLAlchemy/pytest, không có MySQL). Vì vậy **bộ test (tests/) đã viết nhưng chưa được chạy**, ứng dụng chưa được khởi động thật và **chưa kết nối MySQL thật**. Hãy chạy `pytest` ngay sau khi cài; nếu có lỗi nhỏ ở lần chạy đầu, đó là phần chưa được xác minh.
- **File `figma_demo_UI.pdf` không có trong gói tải lên**, nên giao diện bám theo 3 template + CSS có sẵn và danh sách màn hình trong yêu cầu. Cần đối chiếu lại với PDF.

## Hiện trạng ZIP gốc (đã phân tích)
| File | Trạng thái | Xử lý |
|---|---|---|
| `manage.py`, `giaytuan_web/*`, `shop/*` (Django) | **0 byte** | Bỏ, thay bằng Flask (không có code để tái sử dụng) |
| `templates/index.html` | Hoàn chỉnh | → `index.html` + `base.html` + `partials/` (JS menu chuyển vào `static/js/main.js`) |
| `templates/product_detail.html` | CSS nội tuyến, dữ liệu cứng, nút "Make Swap Offer" | → `shop/product_detail.html` dữ liệu từ DB; bỏ "Swap Offer" (không thuộc yêu cầu) |
| `templates/dashboard.html` | Số 0 cứng, mục "Đổi trả" | → `account/dashboard.html` số liệu thật; thay "Đổi trả" bằng Đang xử lý/Hoàn thành (yêu cầu không có đổi trả) |
| `templates/login.html`, `static/js/main.js` | **Trống** | Triển khai mới |
| `static/css/style.css`, `static/images/*` | Hoàn chỉnh | Giữ nguyên; thêm `app.css` |

Ảnh sản phẩm GXHU-A20B không có trong ZIP → hiển thị placeholder "Chưa có ảnh" (tải ảnh qua trang quản trị).

## Cài đặt trên Windows
1. Cài **Python 3.11+** (python.org, tick "Add Python to PATH") và **MySQL 8** (MySQL Installer).
2. Mở PowerShell tại thư mục dự án:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```
3. Tạo database và user (MySQL Command Line Client):
```sql
CREATE DATABASE giaytuan CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'giaytuan_user'@'localhost' IDENTIFIED BY 'DoiMatKhauNay';
GRANT ALL PRIVILEGES ON giaytuan.* TO 'giaytuan_user'@'localhost';
```
4. Sửa `.env`: `SECRET_KEY` (sinh bằng `python -c "import secrets; print(secrets.token_hex(32))"`), `DB_USER`, `DB_PASSWORD`, `DB_NAME`.
5. Tạo bảng – **chọn một cách**:
   - **Migration (khuyến nghị):**
     ```powershell
     $env:FLASK_APP="run.py"
     flask db init
     flask db migrate -m "initial"
     flask db upgrade
     ```
   - **SQL thuần:** `mysql -u root -p < database/schema.sql` (tạo luôn database; sau đó nếu muốn dùng migration hãy `flask db init`, `flask db migrate`, `flask db stamp head`).
6. Nhập dữ liệu mẫu và tạo admin:
```powershell
flask seed            # thêm --demo để có thêm sản phẩm/bài viết [DEMO]
flask create-admin    # hỏi email + mật khẩu (nhập ẩn). Không có mật khẩu mặc định nào trong code.
python run.py         # http://127.0.0.1:5000
```
Admin đăng nhập ở `/login` rồi vào `/admin`.

## Chạy kiểm thử
```powershell
pytest
```
Mặc định dùng SQLite trong bộ nhớ (DB riêng, không đụng dữ liệu thật). Để test trên MySQL, tạo database `giaytuan_test` và đặt `TEST_DATABASE_URL` trong `.env`.

## Cấu trúc
```
app/ __init__.py (factory, CLI) · extensions.py · models/ · routes/ (main, auth, account, cart, admin)
     services/ (auth, catalog, cart, order, dashboard, review) · utils/ · templates/ · static/
database/ schema.sql · seed.py     tests/     config.py  run.py  requirements.txt  .env.example
```

## Chức năng
Sản phẩm (lọc danh mục/thương hiệu, tìm theo tên/mã, phân trang, chi tiết, size/màu/tồn kho, liên quan, đánh giá chỉ khi đã nhận hàng) · Đăng ký/đăng nhập/đăng xuất, hồ sơ, địa chỉ, đổi mật khẩu · Giỏ hàng lưu DB (cần đăng nhập) · Đặt hàng COD trong 1 transaction, trừ kho nguyên tử (`UPDATE ... WHERE stock >= qty`), lưu snapshot giá/địa chỉ · Dashboard khách (số liệu thật), chi tiết/hủy đơn (chỉ khi "Chờ xác nhận", hoàn lại kho) · Liên hệ, blog (chỉ bài đã xuất bản) · Admin: tổng quan, CRUD sản phẩm/danh mục/thương hiệu, ảnh, biến thể & tồn kho, khách hàng (khóa/mở), đơn hàng (luồng trạng thái hợp lệ, thanh toán cần ghi chú xác minh), blog, liên hệ.

## Bảo mật
Hash mật khẩu Werkzeug · CSRF token tự cài đặt cho mọi POST · ORM (chống SQL injection) · Jinja autoescape, blog render qua escape · cookie HttpOnly/SameSite, `Secure` ở production · chống open-redirect ở `next` · admin chặn bằng `before_request` · không có đường nâng quyền qua web (chỉ `flask create-admin`) · upload ảnh: kiểm đuôi, chữ ký file, ≤5 MB, tên ngẫu nhiên · header nosniff/X-Frame-Options.

## Giả định & giới hạn
- **Thanh toán:** chỉ COD. Không có cổng online; không tự sinh mã giao dịch. Admin chỉ đánh dấu "Đã thanh toán" khi đơn đang giao/hoàn thành và có ghi chú xác minh.
- Phí giao hàng (30.000 ₫, miễn phí từ 1.000.000 ₫) là **giả định**, đổi trong `.env`. Chưa có mã giảm giá (cột `discount_amount` = 0).
- Seed: size 39–43 và tồn kho mẫu (mặc định 10) cho GXHU-A20B là **giả định** do ZIP không có; chỉnh trong admin. Giá 810.000 ₫ lấy từ `product_detail.html` gốc.
- Link "Classic/Modern/Sport" ở trang chủ trỏ tới danh mục Giày nam / Giày thể thao (giả định). Nội dung trang Giới thiệu được viết từ thông tin footer/ảnh có sẵn, cần chủ shop duyệt.
- Giỏ hàng chỉ dành cho người đã đăng nhập. Chưa có giới hạn thử đăng nhập sai, quên mật khẩu/email xác nhận, yêu cầu đổi trả.
- Logo/ảnh thương hiệu trong admin nhập theo đường dẫn tương đối trong `static/` (chưa có upload logo).
- Phần phản hồi (responsive) mới viết CSS, chưa được kiểm tra trên trình duyệt thật.
