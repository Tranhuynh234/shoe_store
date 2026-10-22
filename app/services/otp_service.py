"""Deprecated compatibility module.

OTP không được giữ trong bộ nhớ tiến trình hoặc gửi qua mock. Luồng chính sử dụng
PasswordResetOTP trong database và adapter SMS thực tế tại app.services.sms_service.
Các route mới nằm trong app.routes.auth.
"""
