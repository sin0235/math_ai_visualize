import io

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
