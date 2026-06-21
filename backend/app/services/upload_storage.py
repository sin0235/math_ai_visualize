from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from fastapi import UploadFile

from app.core.config import Settings, get_settings
from app.db.session import DatabaseClient
from app.repositories.uploads import UploadRepository, UploadedFileRecord
from app.services import appwrite_storage, r2_storage

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}


@dataclass(frozen=True)
class StoredImage:
    file_id: str
    filename: str
    content_type: str
    data_url: str
    size: int
    public_url: str | None = None
    storage_key: str | None = None
    storage_provider: str = "database"
    storage_bucket: str | None = None
    external_file_id: str | None = None


@dataclass(frozen=True)
class RemoteUpload:
    provider: str
    storage_key: str | None = None
    public_url: str | None = None
    storage_bucket: str | None = None
    external_file_id: str | None = None
    metadata: dict[str, Any] | None = None


async def read_upload_image(upload: UploadFile, settings: Settings) -> StoredImage:
    filename, content_type, body = await read_upload_body(upload, settings)
    encoded = base64.b64encode(body).decode("ascii")
    return StoredImage(
        file_id=hashlib.sha256(body).hexdigest(),
        filename=filename,
        content_type=content_type,
        data_url=f"data:{content_type};base64,{encoded}",
        size=len(body),
    )


async def save_upload_image(upload: UploadFile, settings: Settings, db: DatabaseClient, user_id: str | None = None) -> StoredImage:
    filename, content_type, body = await read_upload_body(upload, settings)
    encoded = base64.b64encode(body).decode("ascii")
    digest = hashlib.sha256(body).hexdigest()
    remote = await store_remote_file_with_fallback(body, filename, content_type, settings)
    stored_base64 = encoded if should_retain_base64(remote, settings) else ""
    record = await UploadRepository(db).create(
        user_id,
        filename,
        content_type,
        len(body),
        digest,
        stored_base64,
        remote.storage_key,
        remote.public_url,
        remote.provider,
        remote.storage_bucket,
        remote.external_file_id,
        json.dumps(remote.metadata or {}, ensure_ascii=False) if remote.metadata else None,
    )
    return stored_image_from_record(record, encoded)


async def load_upload_image(db: DatabaseClient, file_id: str, settings: Settings | None = None) -> StoredImage | None:
    record = await UploadRepository(db).load(file_id)
    if record is None:
        return None
    body = await load_upload_body_from_record(record, settings or get_settings())
    data_base64 = base64.b64encode(body).decode("ascii")
    return stored_image_from_record(record, data_base64)


async def load_upload_body_from_record(record: UploadedFileRecord, settings: Settings) -> bytes:
    if record.data_base64:
        try:
            body = base64.b64decode(record.data_base64, validate=True)
        except (binascii.Error, ValueError) as error:
            raise RuntimeError("File upload trong database có base64 không hợp lệ.") from error
    else:
        body = await load_remote_upload_body(record, settings)
    verify_upload_body(record, body)
    return body


async def read_upload_body(upload: UploadFile, settings: Settings) -> tuple[str, str, bytes]:
    content_type = (upload.content_type or "").lower()
    if content_type not in SUPPORTED_IMAGE_TYPES:
        raise ValueError("File OCR phải là ảnh PNG/JPEG/WebP/GIF.")
    body = await upload.read()
    if not body:
        raise ValueError("File OCR không có dữ liệu.")
    max_bytes = max(1, int(settings.ocr_image_max_mb)) * 1024 * 1024
    if len(body) > max_bytes:
        raise ValueError(f"Ảnh OCR vượt quá giới hạn {settings.ocr_image_max_mb}MB.")
    filename = upload.filename or "ocr-image"
    return filename, content_type, body


async def store_remote_file_with_fallback(body: bytes, filename: str, content_type: str, settings: Settings) -> RemoteUpload:
    provider = settings.ocr_upload_storage_provider
    if provider == "database":
        return RemoteUpload(provider="database")

    if provider in {"auto", "appwrite"} and appwrite_storage.appwrite_configured(settings):
        try:
            stored = await appwrite_storage.store_file(body, filename, content_type, settings)
            return RemoteUpload(
                provider="appwrite",
                storage_key=stored.storage_key,
                public_url=stored.public_url,
                storage_bucket=stored.bucket_id,
                external_file_id=stored.file_id,
                metadata=stored.metadata,
            )
        except Exception as error:
            if provider == "appwrite" and not r2_storage.r2_configured(settings):
                raise RuntimeError(f"Không thể upload Appwrite: {_short_error(str(error))}") from error
            logger.warning("Appwrite upload failed, falling back if possible: %s", _short_error(str(error)))

    if provider in {"auto", "appwrite", "r2"} and r2_storage.r2_configured(settings):
        try:
            storage_key = r2_storage.store_file(body, filename, content_type, settings)
            return RemoteUpload(
                provider="r2",
                storage_key=storage_key,
                public_url=r2_storage.public_url(settings, storage_key),
                storage_bucket=settings.r2_bucket_name,
            )
        except Exception as error:
            if provider == "r2":
                raise RuntimeError(f"Không thể upload R2: {_short_error(str(error))}") from error
            logger.warning("R2 upload failed, falling back to database storage: %s", _short_error(str(error)))

    if provider in {"appwrite", "r2"}:
        raise RuntimeError(f"Storage provider {provider} chưa được cấu hình đầy đủ.")
    return RemoteUpload(provider="database")


async def load_remote_upload_body(record: UploadedFileRecord, settings: Settings) -> bytes:
    if record.storage_provider == "r2":
        if not record.storage_key:
            raise RuntimeError("File upload R2 không có storage key.")
        return r2_storage.load_file(record.storage_key, settings)
    if record.storage_provider == "appwrite":
        if not record.external_file_id:
            raise RuntimeError("File upload Appwrite không có external file id.")
        return await appwrite_storage.load_file(record.external_file_id, settings, record.storage_bucket)
    raise RuntimeError("File upload không còn lưu base64 trong database cho provider này.")


async def delete_remote_upload(record: UploadedFileRecord, settings: Settings) -> None:
    if record.storage_provider == "r2":
        if not record.storage_key:
            raise RuntimeError("File upload R2 không có storage key.")
        r2_storage.delete_file(record.storage_key, settings)
        return
    if record.storage_provider == "appwrite":
        if not record.external_file_id:
            raise RuntimeError("File upload Appwrite không có external file id.")
        await appwrite_storage.delete_file(record.external_file_id, settings, record.storage_bucket)
        return
    raise RuntimeError("File upload không dùng remote storage.")


def verify_upload_body(record: UploadedFileRecord, body: bytes) -> None:
    if len(body) != record.size:
        raise RuntimeError("File upload remote không khớp kích thước đã lưu.")
    digest = hashlib.sha256(body).hexdigest()
    if digest != record.sha256:
        raise RuntimeError("File upload remote không khớp checksum đã lưu.")


def should_retain_base64(remote: RemoteUpload, settings: Settings) -> bool:
    if settings.ocr_upload_base64_retention != "external_only":
        return True
    return remote.provider not in {"appwrite", "r2"}


def stored_image_from_record(record: UploadedFileRecord, data_base64: str) -> StoredImage:
    return StoredImage(
        file_id=record.id,
        filename=record.filename,
        content_type=record.content_type,
        data_url=f"data:{record.content_type};base64,{data_base64}",
        size=record.size,
        public_url=record.public_url,
        storage_key=record.storage_key,
        storage_provider=record.storage_provider,
        storage_bucket=record.storage_bucket,
        external_file_id=record.external_file_id,
    )


def _short_error(message: str) -> str:
    clean = " ".join(message.split())
    return clean[:240] + ("..." if len(clean) > 240 else "")
