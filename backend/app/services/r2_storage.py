import hashlib
from dataclasses import dataclass
from uuid import uuid4

import boto3
from botocore.client import Config
from fastapi import UploadFile

from app.core.config import Settings, get_settings
from app.db.session import DatabaseClient

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
    storage_key: str | None = None


async def read_upload_image(upload: UploadFile, settings: Settings) -> StoredImage:
    from app.services.upload_storage import read_upload_image as read_upload_image_impl

    return await read_upload_image_impl(upload, settings)


async def save_upload_image(upload: UploadFile, settings: Settings, db: DatabaseClient, user_id: str | None = None) -> StoredImage:
    from app.services.upload_storage import save_upload_image as save_upload_image_impl

    return await save_upload_image_impl(upload, settings, db, user_id)


async def load_upload_image(db: DatabaseClient, file_id: str, settings: Settings | None = None) -> StoredImage | None:
    from app.services.upload_storage import load_upload_image as load_upload_image_impl

    return await load_upload_image_impl(db, file_id, settings)


async def read_upload_body(upload: UploadFile) -> tuple[str, str, bytes]:
    from app.services.upload_storage import read_upload_body as read_upload_body_impl

    return await read_upload_body_impl(upload, get_settings())


def store_file_if_configured(body: bytes, filename: str, content_type: str, settings: Settings) -> str | None:
    if not r2_configured(settings):
        return None
    return store_file(body, filename, content_type, settings)


def r2_configured(settings: Settings) -> bool:
    return all([settings.r2_account_id, settings.r2_access_key_id, settings.r2_secret_access_key, settings.r2_bucket_name])


def store_file(body: bytes, filename: str, content_type: str, settings: Settings) -> str:
    require_r2_config(settings)
    object_key = build_object_key(body, filename, settings)
    client = r2_client(settings)
    client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=object_key,
        Body=body,
        ContentType=content_type,
    )
    return object_key


def load_file(object_key: str, settings: Settings) -> bytes:
    require_r2_config(settings)
    response = r2_client(settings).get_object(Bucket=settings.r2_bucket_name, Key=object_key)
    body = response.get("Body")
    if body is None or not hasattr(body, "read"):
        raise RuntimeError("R2 trả về dữ liệu file không hợp lệ.")
    data = body.read()
    if not isinstance(data, bytes):
        raise RuntimeError("R2 trả về dữ liệu file không phải bytes.")
    return data


def r2_client(settings: Settings):
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


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
