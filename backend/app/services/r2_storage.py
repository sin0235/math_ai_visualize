import base64
import hashlib
from dataclasses import dataclass
from uuid import uuid4

import boto3
from botocore.client import Config
from fastapi import UploadFile

from app.core.config import Settings

SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class StoredImage:
    file_id: str
    filename: str
    content_type: str
    data_url: str
    size: int
    public_url: str | None = None


async def read_upload_image(upload: UploadFile, settings: Settings) -> StoredImage:
    content_type = (upload.content_type or "").lower()
    if content_type not in SUPPORTED_IMAGE_TYPES:
        raise ValueError("File OCR phải là ảnh PNG/JPEG/WebP/GIF.")
    body = await upload.read()
    if len(body) > MAX_IMAGE_BYTES:
        raise ValueError("Ảnh OCR vượt quá giới hạn 5MB.")
    filename = upload.filename or "ocr-image"
    object_key = store_file(body, filename, content_type, settings)
    encoded = base64.b64encode(body).decode("ascii")
    return StoredImage(
        file_id=object_key,
        filename=filename,
        content_type=content_type,
        data_url=f"data:{content_type};base64,{encoded}",
        size=len(body),
        public_url=public_url(settings, object_key),
    )


def store_file(body: bytes, filename: str, content_type: str, settings: Settings) -> str:
    require_r2_config(settings)
    object_key = build_object_key(body, filename, settings)
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=object_key,
        Body=body,
        ContentType=content_type,
    )
    return object_key


def require_r2_config(settings: Settings) -> None:
    missing = [
        name
        for name, value in {
            "R2_ACCOUNT_ID": settings.r2_account_id,
            "R2_ACCESS_KEY_ID": settings.r2_access_key_id,
            "R2_SECRET_ACCESS_KEY": settings.r2_secret_access_key,
            "R2_BUCKET_NAME": settings.r2_bucket_name,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"R2 storage is required but missing: {', '.join(missing)}")


def build_object_key(body: bytes, filename: str, settings: Settings) -> str:
    digest = hashlib.sha256(body).hexdigest()[:24]
    safe_name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].strip() or "image"
    prefix = settings.r2_upload_prefix.strip("/") or "uploads"
    return f"{prefix}/ocr/{digest}-{uuid4().hex[:8]}-{safe_name}"


def public_url(settings: Settings, object_key: str) -> str | None:
    if not settings.r2_public_base_url:
        return None
    return f"{settings.r2_public_base_url.rstrip('/')}/{object_key}"
