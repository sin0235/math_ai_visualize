from __future__ import annotations

import base64
import re
from io import BytesIO


_IMAGE_DATA_URL_RE = re.compile(r"^data:image/(png|jpeg|jpg|webp|gif);base64,([A-Za-z0-9+/=\s]+)$", re.IGNORECASE)


def decode_image_data_url(image_data_url: str) -> bytes:
    match = _IMAGE_DATA_URL_RE.match(image_data_url.strip())
    if not match:
        raise ValueError("Ảnh OCR phải là data URL base64 dạng PNG/JPEG/WebP/GIF.")
    encoded = re.sub(r"\s+", "", match.group(2))
    try:
        return base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise ValueError("Dữ liệu ảnh OCR không phải base64 hợp lệ.") from error


def load_pil_image(image_data_url: str):
    try:
        from PIL import Image, ImageOps
    except ImportError as error:
        raise RuntimeError("Thiếu dependency Pillow để chạy local OCR.") from error

    image_bytes = decode_image_data_url(image_data_url)
    try:
        image = Image.open(BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)
        return image.convert("RGB")
    except Exception as error:
        raise ValueError("Không đọc được dữ liệu ảnh OCR.") from error
