import re
from urllib.parse import urljoin, urlparse
from flask import request

PHONE_RE = re.compile(r"^0[35789]\d{8}$")
SLUG_RE = re.compile(r"[^a-z0-9]+")


def clean(value, max_len=None) -> str:
    value = (value or "").strip()
    return value[:max_len] if max_len else value


def normalize_phone(phone: str) -> str:
    s = re.sub(r"[\s.\-()]", "", phone or "")
    if s.startswith("+84"):
        s = "0" + s[3:]
    elif s.startswith("0084"):
        s = "0" + s[4:]
    elif s.startswith("84") and len(s) == 11:
        s = "0" + s[2:]
    return s


def valid_phone(phone: str) -> bool:
    return bool(PHONE_RE.match(normalize_phone(phone)))

def mask_phone(phone: str) -> str:
    p = phone or ""
    return f"{p[:4]}***{p[-3:]}" if len(p) >= 8 else "***"


def validate_password(password: str):
    if len(password or "") < 8:
        return "Mật khẩu phải có ít nhất 8 ký tự."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Mật khẩu phải gồm cả chữ và số."
    if len(password) > 128:
        return "Mật khẩu quá dài."
    return None


def slugify(text: str) -> str:
    import unicodedata
    text = (text or "").replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return SLUG_RE.sub("-", text).strip("-")[:200] or "item"


def parse_int(value, default=None, minimum=None, maximum=None):
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    if minimum is not None and n < minimum:
        return default
    if maximum is not None and n > maximum:
        return default
    return n


def is_safe_redirect(target: str) -> bool:
    if not target:
        return False
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc
