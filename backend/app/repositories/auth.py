from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import uuid4

from passlib.context import CryptContext

from app.db.models import DbRow, SessionRecord, UserRecord
from app.db.session import DatabaseClient

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SESSION_COOKIE_NAME = "hinh_session"
SESSION_DAYS = 30


class UserRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(self, email: str, password: str) -> UserRecord:
        user_id = str(uuid4())
        password_hash = pwd_context.hash(password)
        await self.db.execute(
            "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
            [user_id, email.lower(), password_hash],
        )
        row = await self.db.fetch_one("SELECT * FROM users WHERE id = ?", [user_id])
        if row is None:
            raise RuntimeError("Không thể tạo tài khoản.")
        return user_from_row(row)

    async def find_by_email(self, email: str) -> UserRecord | None:
        row = await self.db.fetch_one("SELECT * FROM users WHERE email = ?", [email.lower()])
        return user_from_row(row) if row else None

    async def find_by_id(self, user_id: str) -> UserRecord | None:
        row = await self.db.fetch_one("SELECT * FROM users WHERE id = ?", [user_id])
        return user_from_row(row) if row else None

    def verify_password(self, password: str, password_hash: str) -> bool:
        return pwd_context.verify(password, password_hash)


class SessionRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(self, user_id: str) -> tuple[SessionRecord, str]:
        session_id = str(uuid4())
        token = token_urlsafe(32)
        token_hash = hash_token(token)
        expires_at = (datetime.now(UTC) + timedelta(days=SESSION_DAYS)).isoformat()
        await self.db.execute(
            "INSERT INTO sessions (id, user_id, token_hash, expires_at) VALUES (?, ?, ?, ?)",
            [session_id, user_id, token_hash, expires_at],
        )
        row = await self.db.fetch_one("SELECT * FROM sessions WHERE id = ?", [session_id])
        if row is None:
            raise RuntimeError("Không thể tạo phiên đăng nhập.")
        return session_from_row(row), token

    async def find_by_token(self, token: str) -> SessionRecord | None:
        row = await self.db.fetch_one("SELECT * FROM sessions WHERE token_hash = ?", [hash_token(token)])
        if row is None:
            return None
        session = session_from_row(row)
        if parse_datetime(session.expires_at) <= datetime.now(UTC):
            await self.delete_by_token(token)
            return None
        return session

    async def delete_by_token(self, token: str) -> None:
        await self.db.execute("DELETE FROM sessions WHERE token_hash = ?", [hash_token(token)])


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def user_from_row(row: DbRow) -> UserRecord:
    return UserRecord(
        id=str(row["id"]),
        email=str(row["email"]),
        password_hash=str(row["password_hash"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def session_from_row(row: DbRow) -> SessionRecord:
    return SessionRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        token_hash=str(row["token_hash"]),
        expires_at=str(row["expires_at"]),
        created_at=str(row["created_at"]),
    )
