"""Chuyển nội dung bài blog (văn bản có đánh dấu) <-> danh sách các mục.

Cú pháp lưu trong cột `content`:

    ## Tiêu đề mục            (cấp 1, tách mục mới)

    ### Tiêu đề 2              (cấp 2, nằm trong mục)

    #### Tiêu đề 3             (cấp 3, nằm trong mục)

    Đoạn văn 1 (cách một dòng trống để sang đoạn).

    [ảnh: uploads/blog/abc.jpg | phải | Chú thích ảnh]

`vị trí` là: trái / phải (ảnh cạnh chữ) hoặc rộng (ảnh trải ngang). Ảnh đầu tiên của mục dùng vị trí này,
các ảnh sau của cùng mục tự xếp thành hàng ảnh nhỏ bên dưới.
"""
import re

_IMG_RE = re.compile(r"^\[\s*ảnh\s*:\s*(.*?)\s*\]$", re.IGNORECASE)
_HEAD_RE = re.compile(r"^(#{2,})\s*(.*?)\s*#*\s*$")
_PATH_RE = re.compile(r"^(images|uploads)/[A-Za-z0-9_\-./']+$")
POSITIONS = ("trái", "phải", "rộng")
_ALIASES = {"left": "trái", "right": "phải", "wide": "rộng", "full": "rộng", "trai": "trái", "phai": "phải",
            "rong": "rộng"}


def _clean_path(path: str) -> str:
    path = (path or "").strip().lstrip("/")
    if path.startswith("static/"):
        path = path[len("static/"):]
    return path if _PATH_RE.match(path) and ".." not in path else ""


def _parse_image(inner: str):
    parts = [p.strip() for p in inner.split("|")]
    path = _clean_path(parts[0])
    if not path:
        return None
    pos = ""
    caption = ""
    for extra in parts[1:2]:
        low = extra.lower()
        low = _ALIASES.get(low, low)
        if low in POSITIONS:
            pos = low
        else:
            caption = extra  # không phải vị trí thì coi là chú thích
    if len(parts) > 2:
        caption = " | ".join(p for p in parts[2:] if p) or caption
    return {"path": path, "pos": pos, "caption": caption}


def parse_blog(content: str, alternate: bool = True) -> list:
    """Trả về [{heading, paragraphs, blocks, text, images:[{path,pos,caption}]}, ...].

    `##` = tiêu đề mục (cấp 1); `###` = tiêu đề 2; `####` trở lên = tiêu đề 3.
    blocks: danh sách theo đúng thứ tự viết, mỗi phần tử là
        {"type": "p", "text": ...}  hoặc  {"type": "h", "level": 2 | 3, "text": ...}
    text: nội dung thô (giữ nguyên ### / ####) để dựng lại form soạn bài.

    alternate=True: ảnh đầu của mỗi mục chưa chọn vị trí sẽ tự luân phiên phải/trái cho trang đọc đỡ đơn điệu.
    alternate=False: giữ nguyên (dùng khi dựng lại form soạn bài)."""
    sections, cur = [], None

    def new(heading=""):
        return {"heading": heading, "paragraphs": [], "blocks": [], "images": []}

    lines = (content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    buf = []

    def flush_paragraph():
        if buf and cur is not None:
            txt = "\n".join(buf).strip()
            if txt:
                cur["paragraphs"].append(txt)
                cur["blocks"].append({"type": "p", "text": txt})
        buf.clear()

    for raw in lines:
        line = raw.strip()
        hm = _HEAD_RE.match(line)
        if hm:
            level, title = len(hm.group(1)), hm.group(2)
            if level == 2:                       # ## = tiêu đề mục
                flush_paragraph()
                if cur is not None:
                    sections.append(cur)
                cur = new(title)
                continue
            if cur is None:                      # tiêu đề phụ nằm trước mọi mục
                cur = new()
            flush_paragraph()
            if title:
                cur["blocks"].append({"type": "h", "level": 2 if level == 3 else 3, "text": title})
            continue
        if cur is None:
            if not line:
                continue
            cur = new()
        m = _IMG_RE.match(line)
        if m:
            flush_paragraph()
            img = _parse_image(m.group(1))
            if img:
                cur["images"].append(img)
            continue
        if not line:
            flush_paragraph()
        else:
            buf.append(line)
    if cur is not None:
        flush_paragraph()
        sections.append(cur)

    sections = [s for s in sections if s["heading"] or s["blocks"] or s["images"]]
    flip = 0
    for s in sections:
        parts = []
        for b in s["blocks"]:
            if b["type"] == "h":
                parts.append(("###" if b["level"] == 2 else "####") + " " + b["text"])
            else:
                parts.append(b["text"])
        s["text"] = "\n\n".join(parts)
        if alternate and s["images"] and not s["images"][0]["pos"]:
            s["images"][0]["pos"] = "phải" if flip % 2 == 0 else "trái"
            flip += 1
    return sections


def _one_line(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("|", "/").replace("[", "(").replace("]", ")")).strip()


def serialize_blog(sections: list) -> str:
    """Ngược lại của parse_blog (dùng để kiểm thử; trình soạn bài làm việc này bằng JS)."""
    out = []
    for s in sections:
        block = []
        if s.get("heading"):
            block.append("## " + _one_line(s["heading"]))
        text = "\n".join(l.rstrip() for l in (s.get("text") or "\n\n".join(s.get("paragraphs", []))).split("\n"))
        text = re.sub(r"^\s*##(?!#)", "#", text, flags=re.M).strip()
        if text:
            block.append(text)
        for img in s.get("images", []):
            path = _clean_path(img.get("path"))
            if path:
                block.append(f"[ảnh: {path} | {img.get('pos') or 'phải'} | {_one_line(img.get('caption'))}]")
        if block:
            out.append("\n\n".join(block))
    return "\n\n".join(out)