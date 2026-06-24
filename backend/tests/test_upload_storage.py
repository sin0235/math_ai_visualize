import io
import json

import pytest
from fastapi import UploadFile

from app.core.config import Settings
from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient
from app.repositories.uploads import UploadedFileRecord
from app.services.r2_storage import load_upload_image, save_upload_image
from app.services.storage_diagnostics import check_upload_storage
from app.services.upload_storage import delete_remote_upload, load_upload_body_from_record

PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02\x00\x00\x00\x0bIDATx\xdac\xfc\xff\x1f\x00\x03\x03\x02\x00\xef\xbf\xa7\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
PNG_SHA256 = "4b5c5c92cec3b23e6a294fc0eea43234ef5126c5a64f4c6c531ac8430ab0b844"


@pytest.fixture
async def db(tmp_path):
    client = SQLiteClient(str(tmp_path / "test.db"))
    await apply_sqlite_migrations(client)
    return client


@pytest.mark.anyio
async def test_save_upload_image_persists_data_url_without_r2(db):
    upload = UploadFile(filename="problem.png", file=io.BytesIO(PNG_BYTES), headers={"content-type": "image/png"})

    stored = await save_upload_image(upload, Settings(_env_file=None), db)
    loaded = await load_upload_image(db, stored.file_id)

    assert loaded is not None
    assert loaded.file_id == stored.file_id
    assert loaded.filename == "problem.png"
    assert loaded.content_type == "image/png"
    assert loaded.size == len(PNG_BYTES)
    assert loaded.data_url == f"data:image/png;base64,{PNG_BASE64}"
    assert loaded.storage_key is None
    assert loaded.public_url is None


@pytest.mark.anyio
async def test_save_upload_image_uses_r2_as_primary_storage(db, monkeypatch):
    upload = UploadFile(filename="problem.png", file=io.BytesIO(PNG_BYTES), headers={"content-type": "image/png"})
    settings = Settings(
        _env_file=None,
        r2_account_id="account",
        r2_access_key_id="access",
        r2_secret_access_key="secret",
        r2_bucket_name="bucket",
        r2_public_base_url="https://cdn.example",
    )

    monkeypatch.setattr("app.services.r2_storage.store_file", lambda body, filename, content_type, settings: "uploads/ocr/file.png")

    stored = await save_upload_image(upload, settings, db)
    row = await db.fetch_one("SELECT data_base64, storage_key, public_url FROM uploaded_files WHERE id = ?", [stored.file_id])

    assert stored.data_url == f"data:image/png;base64,{PNG_BASE64}"
    assert stored.storage_key == "uploads/ocr/file.png"
    assert stored.public_url == "https://cdn.example/uploads/ocr/file.png"
    assert stored.storage_provider == "r2"
    assert row is not None
    assert row["data_base64"] == PNG_BASE64
    assert row["storage_key"] == "uploads/ocr/file.png"
    assert row["public_url"] == "https://cdn.example/uploads/ocr/file.png"


@pytest.mark.anyio
async def test_save_upload_image_uses_appwrite_before_r2(db, monkeypatch):
    from app.services.appwrite_storage import AppwriteStoredFile

    upload = UploadFile(filename="problem.png", file=io.BytesIO(PNG_BYTES), headers={"content-type": "image/png"})
    settings = Settings(
        _env_file=None,
        appwrite_endpoint="https://cloud.appwrite.io/v1",
        appwrite_project_id="project",
        appwrite_api_key="secret",
        appwrite_storage_bucket_id="math-lab-storage",
        appwrite_public_base_url="https://appwrite.example/files",
        r2_account_id="account",
        r2_access_key_id="access",
        r2_secret_access_key="secret",
        r2_bucket_name="bucket",
    )
    r2_calls = []

    async def fake_appwrite_store_file(body, filename, content_type, settings):
        assert body == PNG_BYTES
        assert filename == "problem.png"
        assert content_type == "image/png"
        return AppwriteStoredFile(
            storage_key="uploads/ocr/appwrite-file.png",
            file_id="appwrite-file-id",
            bucket_id="math-lab-storage",
            public_url="https://appwrite.example/files/appwrite-file-id",
            metadata={"storage_key": "uploads/ocr/appwrite-file.png"},
        )

    monkeypatch.setattr("app.services.appwrite_storage.store_file", fake_appwrite_store_file)
    monkeypatch.setattr("app.services.r2_storage.store_file", lambda *args, **kwargs: r2_calls.append(args) or "uploads/ocr/r2-file.png")

    stored = await save_upload_image(upload, settings, db)
    row = await db.fetch_one("SELECT storage_provider, storage_key, storage_bucket, external_file_id, remote_metadata_json FROM uploaded_files WHERE id = ?", [stored.file_id])

    assert stored.storage_provider == "appwrite"
    assert stored.storage_key == "uploads/ocr/appwrite-file.png"
    assert stored.public_url == "https://appwrite.example/files/appwrite-file-id"
    assert stored.storage_bucket == "math-lab-storage"
    assert stored.external_file_id == "appwrite-file-id"
    assert r2_calls == []
    assert row is not None
    assert row["storage_provider"] == "appwrite"
    assert row["storage_key"] == "uploads/ocr/appwrite-file.png"
    assert row["storage_bucket"] == "math-lab-storage"
    assert row["external_file_id"] == "appwrite-file-id"
    assert json.loads(row["remote_metadata_json"])["storage_key"] == "uploads/ocr/appwrite-file.png"


@pytest.mark.anyio
async def test_save_upload_image_falls_back_to_r2_when_appwrite_auto_fails(db, monkeypatch):
    upload = UploadFile(filename="problem.png", file=io.BytesIO(PNG_BYTES), headers={"content-type": "image/png"})
    settings = Settings(
        _env_file=None,
        appwrite_endpoint="https://cloud.appwrite.io/v1",
        appwrite_project_id="project",
        appwrite_api_key="secret",
        appwrite_storage_bucket_id="math-lab-storage",
        r2_account_id="account",
        r2_access_key_id="access",
        r2_secret_access_key="secret",
        r2_bucket_name="bucket",
    )

    async def fail_appwrite(*args, **kwargs):
        raise RuntimeError("appwrite unavailable")

    monkeypatch.setattr("app.services.appwrite_storage.store_file", fail_appwrite)
    monkeypatch.setattr("app.services.r2_storage.store_file", lambda body, filename, content_type, settings: "uploads/ocr/r2-file.png")

    stored = await save_upload_image(upload, settings, db)

    assert stored.storage_provider == "r2"
    assert stored.storage_key == "uploads/ocr/r2-file.png"


@pytest.mark.anyio
async def test_save_upload_image_rejects_unconfigured_forced_provider(db):
    upload = UploadFile(filename="problem.png", file=io.BytesIO(PNG_BYTES), headers={"content-type": "image/png"})
    settings = Settings(_env_file=None, ocr_upload_storage_provider="appwrite")

    with pytest.raises(RuntimeError, match="Storage provider appwrite"):
        await save_upload_image(upload, settings, db)


@pytest.mark.anyio
async def test_save_upload_image_rejects_unsupported_type(db):
    upload = UploadFile(filename="problem.txt", file=io.BytesIO(b"fake"), headers={"content-type": "text/plain"})

    with pytest.raises(ValueError, match="File OCR phải là ảnh"):
        await save_upload_image(upload, Settings(_env_file=None), db)


@pytest.mark.anyio
async def test_save_upload_image_rejects_fake_image_payload(db):
    upload = UploadFile(filename="problem.png", file=io.BytesIO(b"not-an-image"), headers={"content-type": "image/png"})

    with pytest.raises(ValueError, match="không phải ảnh"):
        await save_upload_image(upload, Settings(_env_file=None), db)


@pytest.mark.anyio
async def test_save_upload_image_rejects_truncated_png_header(db):
    upload = UploadFile(filename="problem.png", file=io.BytesIO(b"\x89PNG\r\n\x1a\ntruncated"), headers={"content-type": "image/png"})

    with pytest.raises(ValueError, match="hợp lệ"):
        await save_upload_image(upload, Settings(_env_file=None), db)


@pytest.mark.anyio
async def test_save_upload_image_rejects_too_large_image(db):
    upload = UploadFile(filename="problem.png", file=io.BytesIO(b"x" * (1024 * 1024 + 1)), headers={"content-type": "image/png"})
    settings = Settings(_env_file=None, ocr_image_max_mb=1)

    with pytest.raises(ValueError, match="vượt quá giới hạn"):
        await save_upload_image(upload, settings, db)


@pytest.mark.anyio
async def test_load_upload_image_reads_appwrite_when_database_base64_is_empty(db, monkeypatch):
    from app.services.appwrite_storage import AppwriteStoredFile

    upload = UploadFile(filename="problem.png", file=io.BytesIO(PNG_BYTES), headers={"content-type": "image/png"})
    settings = Settings(
        _env_file=None,
        appwrite_endpoint="https://cloud.appwrite.io/v1",
        appwrite_project_id="project",
        appwrite_api_key="secret",
        appwrite_storage_bucket_id="math-lab-storage",
    )

    async def fake_appwrite_store_file(body, filename, content_type, settings):
        return AppwriteStoredFile(
            storage_key="uploads/ocr/appwrite-file.png",
            file_id="appwrite-file-id",
            bucket_id="math-lab-storage",
            public_url=None,
            metadata={},
        )

    async def fake_appwrite_load_file(file_id, settings, bucket_id=None):
        assert file_id == "appwrite-file-id"
        assert bucket_id == "math-lab-storage"
        return PNG_BYTES

    monkeypatch.setattr("app.services.appwrite_storage.store_file", fake_appwrite_store_file)
    monkeypatch.setattr("app.services.appwrite_storage.load_file", fake_appwrite_load_file)

    stored = await save_upload_image(upload, settings, db)
    await db.execute("UPDATE uploaded_files SET data_base64 = '' WHERE id = ?", [stored.file_id])
    loaded = await load_upload_image(db, stored.file_id, settings)

    assert loaded is not None
    assert loaded.data_url == f"data:image/png;base64,{PNG_BASE64}"
    assert loaded.external_file_id == "appwrite-file-id"


@pytest.mark.anyio
async def test_save_upload_image_external_only_clears_base64_for_remote_provider(db, monkeypatch):
    upload = UploadFile(filename="problem.png", file=io.BytesIO(PNG_BYTES), headers={"content-type": "image/png"})
    settings = Settings(
        _env_file=None,
        ocr_upload_base64_retention="external_only",
        r2_account_id="account",
        r2_access_key_id="access",
        r2_secret_access_key="secret",
        r2_bucket_name="bucket",
    )

    monkeypatch.setattr("app.services.r2_storage.store_file", lambda body, filename, content_type, settings: "uploads/ocr/file.png")

    stored = await save_upload_image(upload, settings, db)
    row = await db.fetch_one("SELECT data_base64, storage_provider FROM uploaded_files WHERE id = ?", [stored.file_id])

    assert stored.data_url == f"data:image/png;base64,{PNG_BASE64}"
    assert row is not None
    assert row["storage_provider"] == "r2"
    assert row["data_base64"] == ""


@pytest.mark.anyio
async def test_load_upload_body_from_record_reads_verified_inline_base64():
    record = UploadedFileRecord(
        id="upload-inline",
        user_id="user-1",
        filename="problem.png",
        content_type="image/png",
        size=len(PNG_BYTES),
        sha256=PNG_SHA256,
        data_base64=PNG_BASE64,
        storage_key=None,
        public_url=None,
    )

    body = await load_upload_body_from_record(record, Settings(_env_file=None))

    assert body == PNG_BYTES


@pytest.mark.anyio
async def test_load_upload_body_from_record_rejects_invalid_inline_base64():
    record = UploadedFileRecord(
        id="upload-inline",
        user_id="user-1",
        filename="problem.png",
        content_type="image/png",
        size=len(PNG_BYTES),
        sha256=PNG_SHA256,
        data_base64="not valid base64",
        storage_key=None,
        public_url=None,
    )

    with pytest.raises(RuntimeError, match="base64 không hợp lệ"):
        await load_upload_body_from_record(record, Settings(_env_file=None))


@pytest.mark.anyio
async def test_load_upload_image_rejects_remote_checksum_mismatch(db, monkeypatch):
    upload = UploadFile(filename="problem.png", file=io.BytesIO(PNG_BYTES), headers={"content-type": "image/png"})
    settings = Settings(
        _env_file=None,
        r2_account_id="account",
        r2_access_key_id="access",
        r2_secret_access_key="secret",
        r2_bucket_name="bucket",
    )

    monkeypatch.setattr("app.services.r2_storage.store_file", lambda body, filename, content_type, settings: "uploads/ocr/file.png")
    monkeypatch.setattr("app.services.r2_storage.load_file", lambda object_key, settings: b"different")

    stored = await save_upload_image(upload, settings, db)
    await db.execute("UPDATE uploaded_files SET data_base64 = '' WHERE id = ?", [stored.file_id])

    with pytest.raises(RuntimeError, match="kích thước|checksum"):
        await load_upload_image(db, stored.file_id, settings)


@pytest.mark.anyio
async def test_load_upload_image_reads_r2_when_database_base64_is_empty(db, monkeypatch):
    upload = UploadFile(filename="problem.png", file=io.BytesIO(PNG_BYTES), headers={"content-type": "image/png"})
    settings = Settings(
        _env_file=None,
        r2_account_id="account",
        r2_access_key_id="access",
        r2_secret_access_key="secret",
        r2_bucket_name="bucket",
    )

    monkeypatch.setattr("app.services.r2_storage.store_file", lambda body, filename, content_type, settings: "uploads/ocr/file.png")
    monkeypatch.setattr("app.services.r2_storage.load_file", lambda object_key, settings: PNG_BYTES)

    stored = await save_upload_image(upload, settings, db)
    await db.execute("UPDATE uploaded_files SET data_base64 = '' WHERE id = ?", [stored.file_id])
    loaded = await load_upload_image(db, stored.file_id, settings)

    assert loaded is not None
    assert loaded.data_url == f"data:image/png;base64,{PNG_BASE64}"
    assert loaded.storage_key == "uploads/ocr/file.png"
