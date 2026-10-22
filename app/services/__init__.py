class BusinessError(Exception):
    """Lỗi nghiệp vụ có thông báo thân thiện, hiển thị trực tiếp cho người dùng."""


class ValidationError(BusinessError):
    """Lỗi theo từng trường: fields={"phone": "..."}; general=[...] hiển thị bằng flash."""

    def __init__(self, fields=None, general=None):
        self.fields = dict(fields or {})
        self.general = list(general or [])
        super().__init__(list(self.fields.values()) + self.general)