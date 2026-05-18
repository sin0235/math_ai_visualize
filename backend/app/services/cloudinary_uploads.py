import asyncio
from dataclasses import dataclass

import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

from app.core.config import Settings

ALLOWED_CHAT_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@dataclass(frozen=True)
class CloudinaryImageUpload:
    secure_url: str
    public_id: str
    width: int | None
    height: int | None
    bytes: int | None
    format: str | None


class CloudinaryUploadError(ValueError):
    pass


async def upload_chat_image(file: UploadFile, settings: Settings, conversation_id: str) -> CloudinaryImageUpload:
    if not settings.cloudinary_cloud_name or not settings.cloudinary_api_key or not settings.cloudinary_api_secret:
        raise CloudinaryUploadError("Cloudinary chưa được cấu hình.")
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CHAT_IMAGE_TYPES:
        raise CloudinaryUploadError("Chỉ hỗ trợ ảnh PNG, JPG, WebP hoặc GIF.")
    data = await file.read()
    max_bytes = max(settings.chat_image_max_mb, 1) * 1024 * 1024
    if not data:
        raise CloudinaryUploadError("Ảnh không hợp lệ.")
    if len(data) > max_bytes:
        raise CloudinaryUploadError(f"Ảnh vượt quá {settings.chat_image_max_mb}MB.")

    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    folder = f"{settings.cloudinary_chat_folder.strip('/')}/{conversation_id}"
    try:
        result = await asyncio.to_thread(
            cloudinary.uploader.upload,
            data,
            folder=folder,
            resource_type="image",
            use_filename=False,
            unique_filename=True,
        )
    except Exception as error:
        raise CloudinaryUploadError("Không thể tải ảnh lên Cloudinary.") from error

    secure_url = result.get("secure_url")
    public_id = result.get("public_id")
    if not secure_url or not public_id:
        raise CloudinaryUploadError("Cloudinary không trả về thông tin ảnh hợp lệ.")
    return CloudinaryImageUpload(
        secure_url=str(secure_url),
        public_id=str(public_id),
        width=int(result["width"]) if result.get("width") is not None else None,
        height=int(result["height"]) if result.get("height") is not None else None,
        bytes=int(result["bytes"]) if result.get("bytes") is not None else None,
        format=str(result["format"]) if result.get("format") is not None else None,
    )
