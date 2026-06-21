import io
import json

import pytest
from fastapi import UploadFile

from app.core.config import Settings
from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient
from app.services.r2_storage import load_upload_image, save_upload_image


@pytest.fixture
async def db(tmp_path):
    client = SQLiteClient(str(tmp_path / "test.db"))
    await apply_sqlite_migrations(client)
    return client


@pytest.mark.anyio
async def test_save_upload_image_persists_data_url_without_r2(db):
    upload = UploadFile(filename="problem.png", file=io.BytesIO(b"fake-png"), headers={"content-type": "image/png"})

    stored = await save_upload_image(upload, Settings(_env_file=None), db)
    loaded = await load_upload_image(db, stored.file_id)

    assert loaded is not None
    assert loaded.file_id == stored.file_id
    assert loaded.filename == "problem.png"
    assert loaded.content_type == "image/png"
    assert loaded.size == len(b"fake-png")
    assert loaded.data_url == "data:image/png;base64,ZmFrZS1wbmc="
    assert loaded.storage_key is None
    assert loaded.public_url is None


@pytest.mark.anyio
async def test_save_upload_image_uses_r2_as_primary_storage(db, monkeypatch):
    upload = UploadFile(filename="problem.png", file=io.BytesIO(b"fake-png"), headers={"content-type": "image/png"})
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

    assert stored.data_url == "data:image/png;base64,ZmFrZS1wbmc="
    assert stored.storage_key == "uploads/ocr/file.png"
    assert stored.public_url == "https://cdn.example/uploads/ocr/file.png"
    assert stored.storage_provider == "r2"
    assert row is not None
    assert row["data_base64"] == "ZmFrZS1wbmc="
    assert row["storage_key"] == "uploads/ocr/file.png"
    assert row["public_url"] == "https://cdn.example/uploads/ocr/file.png"


@pytest.mark.anyio
async def test_save_upload_image_uses_appwrite_before_r2(db, monkeypatch):
    from app.services.appwrite_storage import AppwriteStoredFile

    upload = UploadFile(filename="problem.png", file=io.BytesIO(b"fake-png"), headers={"content-type": "image/png"})
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
        assert body == b"fake-png"
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
    upload = UploadFile(filename="problem.png", file=io.BytesIO(b"fake-png"), headers={"content-type": "image/png"})
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
    upload = UploadFile(filename="problem.png", file=io.BytesIO(b"fake-png"), headers={"content-type": "image/png"})
    settings = Settings(_env_file=None, ocr_upload_storage_provider="appwrite")

    with pytest.raises(RuntimeError, match="Storage provider appwrite"):
        await save_upload_image(upload, settings, db)


@pytest.mark.anyio
async def test_save_upload_image_rejects_unsupported_type(db):
    upload = UploadFile(filename="problem.txt", file=io.BytesIO(b"fake"), headers={"content-type": "text/plain"})

    with pytest.raises(ValueError, match="File OCR phải là ảnh"):
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

    upload = UploadFile(filename="problem.png", file=io.BytesIO(b"fake-png"), headers={"content-type": "image/png"})
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
        return b"fake-png"

    monkeypatch.setattr("app.services.appwrite_storage.store_file", fake_appwrite_store_file)
    monkeypatch.setattr("app.services.appwrite_storage.load_file", fake_appwrite_load_file)

    stored = await save_upload_image(upload, settings, db)
    await db.execute("UPDATE uploaded_files SET data_base64 = '' WHERE id = ?", [stored.file_id])
    loaded = await load_upload_image(db, stored.file_id, settings)

    assert loaded is not None
    assert loaded.data_url == "data:image/png;base64,ZmFrZS1wbmc="
    assert loaded.external_file_id == "appwrite-file-id"


@pytest.mark.anyio
async def test_save_upload_image_external_only_clears_base64_for_remote_provider(db, monkeypatch):
    upload = UploadFile(filename="problem.png", file=io.BytesIO(b"fake-png"), headers={"content-type": "image/png"})
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

    assert stored.data_url == "data:image/png;base64,ZmFrZS1wbmc="
    assert row is not None
    assert row["storage_provider"] == "r2"
    assert row["data_base64"] == ""


@pytest.mark.anyio
async def test_load_upload_image_rejects_remote_checksum_mismatch(db, monkeypatch):
    upload = UploadFile(filename="problem.png", file=io.BytesIO(b"fake-png"), headers={"content-type": "image/png"})
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
    upload = UploadFile(filename="problem.png", file=io.BytesIO(b"fake-png"), headers={"content-type": "image/png"})
    settings = Settings(
        _env_file=None,
        r2_account_id="account",
        r2_access_key_id="access",
        r2_secret_access_key="secret",
        r2_bucket_name="bucket",
    )

    monkeypatch.setattr("app.services.r2_storage.store_file", lambda body, filename, content_type, settings: "uploads/ocr/file.png")
    monkeypatch.setattr("app.services.r2_storage.load_file", lambda object_key, settings: b"fake-png")

    stored = await save_upload_image(upload, settings, db)
    await db.execute("UPDATE uploaded_files SET data_base64 = '' WHERE id = ?", [stored.file_id])
    loaded = await load_upload_image(db, stored.file_id, settings)

    assert loaded is not None
    assert loaded.data_url == "data:image/png;base64,ZmFrZS1wbmc="
    assert loaded.storage_key == "uploads/ocr/file.png"
