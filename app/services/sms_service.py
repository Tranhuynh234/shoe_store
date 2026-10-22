"""Gửi SMS OTP. SMS_PROVIDER: esms | speedsms | (trống = chưa cấu hình).
Hai adapter viết theo tài liệu công khai, CHƯA thử với tài khoản thật. Không ghi OTP vào log."""
import base64
import json
import logging
import urllib.error
import urllib.request

from flask import current_app

from app.utils.validators import mask_phone

log = logging.getLogger(__name__)
TEST_OUTBOX: list = []   # chỉ dùng khi app.testing


class SmsError(Exception):
    pass


def _provider() -> str:
    name = (current_app.config.get("SMS_PROVIDER") or "").strip().lower()
    if name == "memory" and not current_app.testing:
        return ""
    return name


def is_configured() -> bool:
    p = _provider()
    if p == "memory":
        return True
    cfg = current_app.config
    if p == "esms":
        return bool(cfg.get("SMS_API_KEY") and cfg.get("SMS_API_SECRET") and cfg.get("SMS_SENDER_ID"))
    if p == "speedsms":
        return bool(cfg.get("SMS_API_KEY"))
    return False


def build_otp_message(code: str, ttl_minutes: int) -> str:
    return current_app.config["SMS_OTP_TEMPLATE"].format(code=code, minutes=ttl_minutes)


def send_otp(phone: str, code: str, ttl_minutes: int) -> None:
    provider = _provider()
    if not is_configured():
        raise SmsError("SMS provider chưa được cấu hình")
    content = build_otp_message(code, ttl_minutes)
    if provider == "memory":
        TEST_OUTBOX.append({"phone": phone, "content": content, "code": code})
        return
    try:
        if provider == "esms":
            _send_esms(phone, content)
        elif provider == "speedsms":
            _send_speedsms(phone, content)
        else:
            raise SmsError(f"SMS_PROVIDER không hợp lệ: {provider!r}")
    except SmsError:
        raise
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        log.error("Gửi SMS tới %s thất bại: %s", mask_phone(phone), type(exc).__name__)
        raise SmsError("Không kết nối được nhà cung cấp SMS") from exc


def _post_json(url: str, payload: dict, headers: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=current_app.config["SMS_TIMEOUT"]) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _send_esms(phone: str, content: str) -> None:
    cfg = current_app.config
    body = _post_json(
        "https://rest.esms.vn/MainService.svc/json/SendMultipleMessage_V4_post_json/",
        {"ApiKey": cfg["SMS_API_KEY"], "SecretKey": cfg["SMS_API_SECRET"], "Phone": phone,
         "Content": content, "Brandname": cfg["SMS_SENDER_ID"], "SmsType": cfg["SMS_TYPE"],
         "IsUnicode": "0", "Sandbox": "1" if cfg["SMS_SANDBOX"] else "0"}, {})
    if str(body.get("CodeResult")) != "100":
        log.error("eSMS từ chối tin gửi tới %s: CodeResult=%s", mask_phone(phone), body.get("CodeResult"))
        raise SmsError("eSMS từ chối yêu cầu gửi tin")


def _send_speedsms(phone: str, content: str) -> None:
    cfg = current_app.config
    token = base64.b64encode(f"{cfg['SMS_API_KEY']}:x".encode()).decode()
    payload = {"to": [phone], "content": content, "sms_type": int(cfg["SMS_TYPE"])}
    if cfg.get("SMS_SENDER_ID"):
        payload["sender"] = cfg["SMS_SENDER_ID"]
    body = _post_json("https://api.speedsms.vn/index.php/sms/send", payload, {"Authorization": f"Basic {token}"})
    if body.get("status") != "success":
        log.error("SpeedSMS từ chối tin gửi tới %s: code=%s", mask_phone(phone), body.get("code"))
        raise SmsError("SpeedSMS từ chối yêu cầu gửi tin")