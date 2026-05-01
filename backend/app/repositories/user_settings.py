from app.db.models import DbRow, UserSettingsRecord
from app.db.session import DatabaseClient


class UserSettingsRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def get(self, user_id: str) -> UserSettingsRecord | None:
        row = await self.db.fetch_one("SELECT * FROM user_settings WHERE user_id = ?", [user_id])
        return user_settings_from_row(row) if row else None

    async def upsert(self, user_id: str, settings_json: str) -> UserSettingsRecord:
        await self.db.execute(
            """
            INSERT INTO user_settings (user_id, settings_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET settings_json = excluded.settings_json, updated_at = CURRENT_TIMESTAMP
            """,
            [user_id, settings_json],
        )
        row = await self.db.fetch_one("SELECT * FROM user_settings WHERE user_id = ?", [user_id])
        if row is None:
            raise RuntimeError("Không thể lưu cấu hình người dùng.")
        return user_settings_from_row(row)


def user_settings_from_row(row: DbRow) -> UserSettingsRecord:
    return UserSettingsRecord(
        user_id=str(row["user_id"]),
        settings_json=str(row["settings_json"]),
        updated_at=str(row["updated_at"]),
    )
