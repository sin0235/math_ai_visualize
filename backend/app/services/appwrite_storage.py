from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from uuid import uuid4

from app.core.config import Settings


@dataclass(frozen=True)
class AppwriteStoredFile:
    storage_key: str
    file_id: str
    bucket_id: str
    public_url: str | None
    metadata: dict


def appwrite_configured(settings: Settings) -> bool:
    return all([
        settings.appwrite_endpoint,
        settings.appwrite_project_id,
        settings.appwrite_api_key,
        settings.appwrite_storage_bucket_id,
    ])


async def store_file(body: bytes, filename: str, content_type: str, settings: Settings) -> AppwriteStoredFile:
    require_appwrite_config(settings)
    safe_name = safe_filename(filename)
    file_id = build_file_id()
    storage_key = build_storage_key(body, safe_name, settings)
    result = await asyncio.to_thread(_store_file_sync, body, safe_name, content_type, file_id, settings)
    return AppwriteStoredFile(
        storage_key=storage_key,
        file_id=file_id,
        bucket_id=settings.appwrite_storage_bucket_id or "",
        public_url=public_url(settings, file_id),
        metadata={"appwrite_file": result, "storage_key": storage_key},
    )


async def load_file(file_id: str, settings: Settings, bucket_id: str | None = None) -> bytes:
    require_appwrite_config(settings)
    return await asyncio.to_thread(_load_file_sync, file_id, settings, bucket_id)


def _store_file_sync(body: bytes, filename: str, content_type: str, file_id: str, settings: Settings) -> dict:
    storage = _storage_client(settings)
    try:
        from appwrite.input_file import InputFile
    except ImportError as error:
        raise RuntimeError("Appwrite SDK chưa được cài đặt trong backend.") from error

    try:
        input_file = InputFile.from_bytes(body, filename=filename, mime_type=content_type)
    except TypeError:
        input_file = InputFile.from_bytes(body, filename=filename)
    created = storage.create_file(
        bucket_id=settings.appwrite_storage_bucket_id or "",
        file_id=file_id,
        file=input_file,
    )
    return dict(created) if isinstance(created, dict) else {"id": file_id}


def _load_file_sync(file_id: str, settings: Settings, bucket_id: str | None) -> bytes:
    storage = _storage_client(settings)
    downloaded = storage.get_file_download(
        bucket_id=bucket_id or settings.appwrite_storage_bucket_id or "",
        file_id=file_id,
    )
    return _download_to_bytes(downloaded)


def _storage_client(settings: Settings):
    try:
        from appwrite.client import Client
        from appwrite.services.storage import Storage
    except ImportError as error:
        raise RuntimeError("Appwrite SDK chưa được cài đặt trong backend.") from error

    client = Client()
    client.set_endpoint((settings.appwrite_endpoint or "").rstrip("/"))
    client.set_project(settings.appwrite_project_id or "")
    client.set_key(settings.appwrite_api_key or "")
    return Storage(client)


def _download_to_bytes(downloaded) -> bytes:
    if isinstance(downloaded, bytes):
        return downloaded
    if isinstance(downloaded, bytearray):
        return bytes(downloaded)
    read = getattr(downloaded, "read", None)
    if callable(read):
        data = read()
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)
    content = getattr(downloaded, "content", None)
    if isinstance(content, bytes):
        return content
    if isinstance(content, bytearray):
        return bytes(content)
    raise RuntimeError("Appwrite trả về dữ liệu file không hợp lệ.")


def require_appwrite_config(settings: Settings) -> None:
    missing = [
        name
        for name, value in {
            "APPWRITE_ENDPOINT": settings.appwrite_endpoint,
            "APPWRITE_PROJECT_ID": settings.appwrite_project_id,
            "APPWRITE_API_KEY": settings.appwrite_api_key,
            "APPWRITE_STORAGE_BUCKET_ID": settings.appwrite_storage_bucket_id,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Appwrite storage is required but missing: {', '.join(missing)}")


def build_file_id() -> str:
    return f"ocr_{uuid4().hex}"


def build_storage_key(body: bytes, filename: str, settings: Settings) -> str:
    digest = hashlib.sha256(body).hexdigest()[:24]
    prefix = settings.appwrite_upload_prefix.strip("/") or "uploads"
    return f"{prefix}/ocr/{digest}-{uuid4().hex[:8]}-{filename}"


def safe_filename(filename: str) -> str:
    return filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].strip() or "image"


def public_url(settings: Settings, file_id: str) -> str | None:
    if not settings.appwrite_public_base_url:
        return None
    return f"{settings.appwrite_public_base_url.rstrip('/')}/{file_id}"
