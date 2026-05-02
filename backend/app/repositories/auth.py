from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import randbelow, token_urlsafe
from uuid import uuid4

from passlib.context import CryptContext

from app.db.models import AuthTokenRecord, DbRow, LegalAcceptanceRecord, OAuthIdentityRecord, OAuthStateRecord, SessionRecord, UserRecord
from app.db.session import DatabaseClient

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SESSION_COOKIE_NAME = "hinh_session"
SESSION_DAYS = 30
TOKEN_PURPOSE_EMAIL_VERIFICATION = "email_verification"
TOKEN_PURPOSE_PASSWORD_RESET = "password_reset"
LEGAL_DOCUMENT_PRIVACY_POLICY = "privacy_policy"
LEGAL_DOCUMENT_TERMS = "terms"
LEGAL_DOCUMENT_PRIVACY_POLICY_VERSION = "2026-05-02"
LEGAL_DOCUMENT_TERMS_VERSION = "2026-05-02"
OAUTH_PROVIDER_GOOGLE = "google"
OAUTH_PASSWORD_SENTINEL = "oauth:google"


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class UserRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(self, email: str, password: str) -> UserRecord:
        user_id = str(uuid4())
        password_hash = pwd_context.hash(password)
        await self.db.execute(
            "INSERT INTO users (id, email, password_hash, password_changed_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            [user_id, normalize_email(email), password_hash],
        )
        row = await self.db.fetch_one("SELECT * FROM users WHERE id = ?", [user_id])
        if row is None:
            raise RuntimeError("Không thể tạo tài khoản.")
        return user_from_row(row)

    async def create_oauth_user(self, email: str, display_name: str | None = None) -> UserRecord:
        user_id = str(uuid4())
        await self.db.execute(
            "INSERT INTO users (id, email, password_hash, display_name, email_verified_at, status) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 'active')",
            [user_id, normalize_email(email), OAUTH_PASSWORD_SENTINEL, display_name],
        )
        row = await self.db.fetch_one("SELECT * FROM users WHERE id = ?", [user_id])
        if row is None:
            raise RuntimeError("Không thể tạo tài khoản Google.")
        return user_from_row(row)

    async def find_by_email(self, email: str) -> UserRecord | None:
        row = await self.db.fetch_one("SELECT * FROM users WHERE email = ?", [normalize_email(email)])
        return user_from_row(row) if row else None

    async def find_by_id(self, user_id: str) -> UserRecord | None:
        row = await self.db.fetch_one("SELECT * FROM users WHERE id = ?", [user_id])
        return user_from_row(row) if row else None

    async def mark_login(self, user_id: str) -> None:
        await self.db.execute(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP, failed_login_count = 0, locked_until = NULL, last_failed_login_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [user_id],
        )

    async def record_failed_login(self, user_id: str) -> UserRecord:
        await self.db.execute(
            "UPDATE users SET failed_login_count = failed_login_count + 1, last_failed_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [user_id],
        )
        user = await self.find_by_id(user_id)
        if user is None:
            raise RuntimeError("Không thể cập nhật lần đăng nhập lỗi.")
        return user

    async def lock_until(self, user_id: str, locked_until: datetime) -> None:
        await self.db.execute("UPDATE users SET locked_until = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", [locked_until.isoformat(), user_id])

    async def clear_failed_login(self, user_id: str) -> None:
        await self.db.execute(
            "UPDATE users SET failed_login_count = 0, locked_until = NULL, last_failed_login_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [user_id],
        )

    async def update_password(self, user_id: str, password: str) -> UserRecord:
        await self.db.execute(
            "UPDATE users SET password_hash = ?, password_changed_at = CURRENT_TIMESTAMP, failed_login_count = 0, locked_until = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [pwd_context.hash(password), user_id],
        )
        user = await self.find_by_id(user_id)
        if user is None:
            raise RuntimeError("Không thể cập nhật mật khẩu.")
        return user

    async def mark_email_verified(self, user_id: str) -> UserRecord:
        await self.db.execute(
            "UPDATE users SET email_verified_at = COALESCE(email_verified_at, CURRENT_TIMESTAMP), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [user_id],
        )
        user = await self.find_by_id(user_id)
        if user is None:
            raise RuntimeError("Không thể xác minh email.")
        return user

    async def ensure_email_verified(self, user_id: str) -> UserRecord:
        return await self.mark_email_verified(user_id)

    async def update_profile(self, user_id: str, display_name: str | None) -> UserRecord:
        await self.db.execute("UPDATE users SET display_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", [display_name, user_id])
        user = await self.find_by_id(user_id)
        if user is None:
            raise RuntimeError("Không thể cập nhật hồ sơ.")
        return user

    def verify_password(self, password: str, password_hash: str) -> bool:
        if not password_hash.startswith("$2"):
            return False
        return pwd_context.verify(password, password_hash)


class SessionRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(self, user_id: str, ip_address: str | None = None, user_agent: str | None = None) -> tuple[SessionRecord, str]:
        session_id = str(uuid4())
        token = token_urlsafe(32)
        token_hash = hash_token(token)
        expires_at = (datetime.now(UTC) + timedelta(days=SESSION_DAYS)).isoformat()
        await self.db.execute(
            "INSERT INTO sessions (id, user_id, token_hash, expires_at, last_seen_at, ip_address, user_agent) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)",
            [session_id, user_id, token_hash, expires_at, ip_address, clean_user_agent(user_agent)],
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
        if session.revoked_at is not None:
            return None
        if parse_datetime(session.expires_at) <= datetime.now(UTC):
            await self.delete_by_token(token)
            return None
        return session

    async def touch(self, session_id: str) -> None:
        await self.db.execute("UPDATE sessions SET last_seen_at = CURRENT_TIMESTAMP WHERE id = ? AND revoked_at IS NULL", [session_id])

    async def list_for_user(self, user_id: str) -> list[SessionRecord]:
        rows = await self.db.fetch_all(
            "SELECT * FROM sessions WHERE user_id = ? AND revoked_at IS NULL AND expires_at > CURRENT_TIMESTAMP ORDER BY last_seen_at DESC, created_at DESC",
            [user_id],
        )
        return [session_from_row(row) for row in rows]

    async def revoke_by_id(self, user_id: str, session_id: str) -> bool:
        session = await self.db.fetch_one("SELECT * FROM sessions WHERE id = ? AND user_id = ? AND revoked_at IS NULL", [session_id, user_id])
        if session is None:
            return False
        await self.db.execute("UPDATE sessions SET revoked_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?", [session_id, user_id])
        return True

    async def revoke_by_token(self, token: str) -> None:
        await self.db.execute("UPDATE sessions SET revoked_at = CURRENT_TIMESTAMP WHERE token_hash = ? AND revoked_at IS NULL", [hash_token(token)])

    async def revoke_all_for_user(self, user_id: str, except_token: str | None = None) -> int:
        sessions = await self.list_for_user(user_id)
        except_hash = hash_token(except_token) if except_token else None
        revoked = 0
        for session in sessions:
            if except_hash and session.token_hash == except_hash:
                continue
            await self.db.execute("UPDATE sessions SET revoked_at = CURRENT_TIMESTAMP WHERE id = ?", [session.id])
            revoked += 1
        return revoked

    async def delete_by_token(self, token: str) -> None:
        await self.db.execute("DELETE FROM sessions WHERE token_hash = ?", [hash_token(token)])


class AuthTokenRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(
        self,
        user_id: str,
        purpose: str,
        ttl_minutes: int,
        ip_address: str | None = None,
        user_agent: str | None = None,
        include_otp: bool = False,
    ) -> tuple[AuthTokenRecord, str] | tuple[AuthTokenRecord, str, str]:
        await self.invalidate_for_user(user_id, purpose)
        token_id = str(uuid4())
        token = token_urlsafe(48)
        otp = generate_otp() if include_otp else None
        expires_at = (datetime.now(UTC) + timedelta(minutes=ttl_minutes)).isoformat()
        await self.db.execute(
            "INSERT INTO auth_tokens (id, user_id, purpose, token_hash, expires_at, created_ip, user_agent, otp_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [token_id, user_id, purpose, hash_token(token), expires_at, ip_address, clean_user_agent(user_agent), hash_token(otp) if otp else None],
        )
        row = await self.db.fetch_one("SELECT * FROM auth_tokens WHERE id = ?", [token_id])
        if row is None:
            raise RuntimeError("Không thể tạo token xác thực.")
        record = auth_token_from_row(row)
        if otp is None:
            return record, token
        return record, token, otp

    async def find_valid_by_token(self, token: str, purpose: str) -> AuthTokenRecord | None:
        row = await self.db.fetch_one("SELECT * FROM auth_tokens WHERE token_hash = ? AND purpose = ?", [hash_token(token), purpose])
        if row is None:
            return None
        record = auth_token_from_row(row)
        if record.consumed_at is not None or parse_datetime(record.expires_at) <= datetime.now(UTC):
            return None
        return record

    async def find_valid_by_token_and_otp(self, token: str, otp: str, purpose: str) -> AuthTokenRecord | None:
        record = await self.find_valid_by_token(token, purpose)
        if record is None or record.otp_hash is None:
            return None
        if record.otp_attempts >= record.max_otp_attempts:
            return None
        if hash_token(otp) != record.otp_hash:
            await self.db.execute("UPDATE auth_tokens SET otp_attempts = otp_attempts + 1 WHERE id = ?", [record.id])
            return None
        return record

    async def consume(self, token_id: str) -> None:
        await self.db.execute("UPDATE auth_tokens SET consumed_at = CURRENT_TIMESTAMP WHERE id = ? AND consumed_at IS NULL", [token_id])

    async def invalidate_for_user(self, user_id: str, purpose: str) -> None:
        await self.db.execute(
            "UPDATE auth_tokens SET consumed_at = CURRENT_TIMESTAMP WHERE user_id = ? AND purpose = ? AND consumed_at IS NULL",
            [user_id, purpose],
        )


class LegalAcceptanceRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def record(self, user_id: str, document_type: str, document_version: str, ip_address: str | None = None, user_agent: str | None = None) -> LegalAcceptanceRecord:
        acceptance_id = str(uuid4())
        await self.db.execute(
            "INSERT INTO legal_acceptances (id, user_id, document_type, document_version, accepted_ip, user_agent) VALUES (?, ?, ?, ?, ?, ?)",
            [acceptance_id, user_id, document_type, document_version, ip_address, clean_user_agent(user_agent)],
        )
        row = await self.db.fetch_one("SELECT * FROM legal_acceptances WHERE id = ?", [acceptance_id])
        if row is None:
            raise RuntimeError("Không thể lưu xác nhận điều khoản.")
        return legal_acceptance_from_row(row)

    async def record_registration_acceptances(self, user_id: str, ip_address: str | None = None, user_agent: str | None = None) -> None:
        await self.record(user_id, LEGAL_DOCUMENT_PRIVACY_POLICY, LEGAL_DOCUMENT_PRIVACY_POLICY_VERSION, ip_address, user_agent)
        await self.record(user_id, LEGAL_DOCUMENT_TERMS, LEGAL_DOCUMENT_TERMS_VERSION, ip_address, user_agent)


class OAuthStateRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(
        self,
        provider: str,
        ttl_minutes: int,
        ip_address: str | None = None,
        user_agent: str | None = None,
        redirect_after: str | None = None,
    ) -> tuple[OAuthStateRecord, str]:
        state = token_urlsafe(32)
        state_hash = hash_token(state)
        expires_at = (datetime.now(UTC) + timedelta(minutes=ttl_minutes)).isoformat()
        await self.db.execute(
            "INSERT INTO oauth_states (state_hash, provider, redirect_after, expires_at, created_ip, user_agent) VALUES (?, ?, ?, ?, ?, ?)",
            [state_hash, provider, redirect_after, expires_at, ip_address, clean_user_agent(user_agent)],
        )
        row = await self.db.fetch_one("SELECT * FROM oauth_states WHERE state_hash = ?", [state_hash])
        if row is None:
            raise RuntimeError("Không thể tạo OAuth state.")
        return oauth_state_from_row(row), state

    async def consume_valid(self, state: str, provider: str) -> OAuthStateRecord | None:
        state_hash = hash_token(state)
        row = await self.db.fetch_one("SELECT * FROM oauth_states WHERE state_hash = ? AND provider = ?", [state_hash, provider])
        if row is None:
            return None
        record = oauth_state_from_row(row)
        if record.consumed_at is not None or parse_datetime(record.expires_at) <= datetime.now(UTC):
            return None
        await self.db.execute("UPDATE oauth_states SET consumed_at = CURRENT_TIMESTAMP WHERE state_hash = ? AND consumed_at IS NULL", [state_hash])
        return record


class OAuthIdentityRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def find_by_provider_subject(self, provider: str, subject: str) -> OAuthIdentityRecord | None:
        row = await self.db.fetch_one("SELECT * FROM oauth_identities WHERE provider = ? AND provider_subject = ?", [provider, subject])
        return oauth_identity_from_row(row) if row else None

    async def find_by_user_provider(self, user_id: str, provider: str) -> OAuthIdentityRecord | None:
        row = await self.db.fetch_one("SELECT * FROM oauth_identities WHERE user_id = ? AND provider = ?", [user_id, provider])
        return oauth_identity_from_row(row) if row else None

    async def create(
        self,
        user_id: str,
        provider: str,
        subject: str,
        email: str,
        email_verified: bool,
        display_name: str | None = None,
        picture_url: str | None = None,
    ) -> OAuthIdentityRecord:
        identity_id = str(uuid4())
        await self.db.execute(
            "INSERT INTO oauth_identities (id, user_id, provider, provider_subject, email, email_verified, display_name, picture_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [identity_id, user_id, provider, subject, normalize_email(email), 1 if email_verified else 0, display_name, picture_url],
        )
        row = await self.db.fetch_one("SELECT * FROM oauth_identities WHERE id = ?", [identity_id])
        if row is None:
            raise RuntimeError("Không thể liên kết Google OAuth.")
        return oauth_identity_from_row(row)

    async def update_from_google(self, identity_id: str, email: str, email_verified: bool, display_name: str | None = None, picture_url: str | None = None) -> OAuthIdentityRecord:
        await self.db.execute(
            "UPDATE oauth_identities SET email = ?, email_verified = ?, display_name = ?, picture_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [normalize_email(email), 1 if email_verified else 0, display_name, picture_url, identity_id],
        )
        row = await self.db.fetch_one("SELECT * FROM oauth_identities WHERE id = ?", [identity_id])
        if row is None:
            raise RuntimeError("Không thể cập nhật Google OAuth.")
        return oauth_identity_from_row(row)


class RateLimitRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = datetime.now(UTC)
        bucket = str(int(now.timestamp()) // window_seconds)
        row = await self.db.fetch_one("SELECT * FROM rate_limit_events WHERE key = ? AND bucket = ?", [key, bucket])
        if row is None:
            expires_at = (now + timedelta(seconds=window_seconds)).isoformat()
            await self.db.execute(
                "INSERT INTO rate_limit_events (key, bucket, count, expires_at) VALUES (?, ?, 1, ?)",
                [key, bucket, expires_at],
            )
            return RateLimitResult(True, max(limit - 1, 0), window_seconds)
        count = int(row.get("count") or 0) + 1
        await self.db.execute("UPDATE rate_limit_events SET count = ?, updated_at = CURRENT_TIMESTAMP WHERE key = ? AND bucket = ?", [count, key, bucket])
        retry_after = max(int((parse_datetime(str(row["expires_at"])) - now).total_seconds()), 1)
        return RateLimitResult(count <= limit, max(limit - count, 0), retry_after)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def generate_otp() -> str:
    return f"{randbelow(1_000_000):06d}"


def clean_user_agent(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    return user_agent[:300]


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def optional_str(row: DbRow, key: str) -> str | None:
    return str(row[key]) if row.get(key) is not None else None


def user_from_row(row: DbRow) -> UserRecord:
    return UserRecord(
        id=str(row["id"]),
        email=str(row["email"]),
        password_hash=str(row["password_hash"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        role=str(row.get("role") or "user"),
        status=str(row.get("status") or "active"),
        display_name=optional_str(row, "display_name"),
        last_login_at=optional_str(row, "last_login_at"),
        plan=str(row.get("plan") or "free"),
        email_verified_at=optional_str(row, "email_verified_at"),
        password_changed_at=optional_str(row, "password_changed_at"),
        failed_login_count=int(row.get("failed_login_count") or 0),
        locked_until=optional_str(row, "locked_until"),
        last_failed_login_at=optional_str(row, "last_failed_login_at"),
    )


def session_from_row(row: DbRow) -> SessionRecord:
    return SessionRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        token_hash=str(row["token_hash"]),
        expires_at=str(row["expires_at"]),
        created_at=str(row["created_at"]),
        last_seen_at=optional_str(row, "last_seen_at"),
        revoked_at=optional_str(row, "revoked_at"),
        ip_address=optional_str(row, "ip_address"),
        user_agent=optional_str(row, "user_agent"),
    )


def auth_token_from_row(row: DbRow) -> AuthTokenRecord:
    return AuthTokenRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        purpose=str(row["purpose"]),
        token_hash=str(row["token_hash"]),
        expires_at=str(row["expires_at"]),
        consumed_at=optional_str(row, "consumed_at"),
        created_at=str(row["created_at"]),
        created_ip=optional_str(row, "created_ip"),
        user_agent=optional_str(row, "user_agent"),
        otp_hash=optional_str(row, "otp_hash"),
        otp_attempts=int(row.get("otp_attempts") or 0),
        max_otp_attempts=int(row.get("max_otp_attempts") or 5),
    )


def legal_acceptance_from_row(row: DbRow) -> LegalAcceptanceRecord:
    return LegalAcceptanceRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        document_type=str(row["document_type"]),
        document_version=str(row["document_version"]),
        accepted_at=str(row["accepted_at"]),
        accepted_ip=optional_str(row, "accepted_ip"),
        user_agent=optional_str(row, "user_agent"),
    )


def oauth_identity_from_row(row: DbRow) -> OAuthIdentityRecord:
    return OAuthIdentityRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        provider=str(row["provider"]),
        provider_subject=str(row["provider_subject"]),
        email=str(row["email"]),
        email_verified=bool(row.get("email_verified")),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        display_name=optional_str(row, "display_name"),
        picture_url=optional_str(row, "picture_url"),
    )


def oauth_state_from_row(row: DbRow) -> OAuthStateRecord:
    return OAuthStateRecord(
        state_hash=str(row["state_hash"]),
        provider=str(row["provider"]),
        expires_at=str(row["expires_at"]),
        created_at=str(row["created_at"]),
        redirect_after=optional_str(row, "redirect_after"),
        consumed_at=optional_str(row, "consumed_at"),
        created_ip=optional_str(row, "created_ip"),
        user_agent=optional_str(row, "user_agent"),
    )
