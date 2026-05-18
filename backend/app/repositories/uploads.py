from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.db.session import DatabaseClient


@dataclass(frozen=True)
class UploadedFileRecord:
    id: str
    user_id: str | None
    filename: str
    content_type: str
    size: int
    sha256: str
    data_base64: str
    storage_key: str | None
    public_url: str | None
    created_at: str | None = None

    @property
    def data_url(self) -> str:
        return f"data:{self.content_type};base64,{self.data_base64}"


class UploadRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(
        self,
        user_id: str | None,
        filename: str,
        content_type: str,
        size: int,
        sha256: str,
        data_base64: str,
        storage_key: str | None = None,
        public_url: str | None = None,
    ) -> UploadedFileRecord:
        upload_id = uuid4().hex
        await self.db.execute(
            """
            INSERT INTO uploaded_files (id, user_id, filename, content_type, size, sha256, data_base64, storage_key, public_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [upload_id, user_id, filename, content_type, size, sha256, data_base64, storage_key, public_url],
        )
        row = await self.db.fetch_one("SELECT * FROM uploaded_files WHERE id = ?", [upload_id])
        if row is None:
            raise RuntimeError("Không thể tải lại file vừa lưu.")
        return uploaded_file_from_row(row)

    async def load(self, upload_id: str) -> UploadedFileRecord | None:
        row = await self.db.fetch_one("SELECT * FROM uploaded_files WHERE id = ?", [upload_id])
        return uploaded_file_from_row(row) if row is not None else None


def uploaded_file_from_row(row: Any) -> UploadedFileRecord:
    return UploadedFileRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]) if row.get("user_id") is not None else None,
        filename=str(row["filename"]),
        content_type=str(row["content_type"]),
        size=int(row["size"]),
        sha256=str(row["sha256"]),
        data_base64=str(row["data_base64"]),
        storage_key=str(row["storage_key"]) if row.get("storage_key") is not None else None,
        public_url=str(row["public_url"]) if row.get("public_url") is not None else None,
        created_at=str(row["created_at"]) if row.get("created_at") is not None else None,
    )
