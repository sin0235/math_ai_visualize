from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class SecretCryptoError(ValueError):
    pass


def generate_user_secret_key() -> str:
    return Fernet.generate_key().decode("ascii")


def encrypt_user_secret(plaintext: str, key: str | None) -> str:
    secret = plaintext.strip()
    if not secret:
        raise SecretCryptoError("API key không được để trống.")
    fernet = _fernet_from_key(key)
    return fernet.encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_user_secret(ciphertext: str | None, key: str | None) -> str:
    if not ciphertext:
        raise SecretCryptoError("Chưa có API key được lưu.")
    fernet = _fernet_from_key(key)
    try:
        return fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError) as error:
        raise SecretCryptoError("Không thể giải mã API key đã lưu.") from error


def api_key_last4(api_key: str) -> str:
    cleaned = api_key.strip()
    return cleaned[-4:] if len(cleaned) >= 4 else cleaned


def ensure_user_secret_key_configured(key: str | None) -> None:
    _fernet_from_key(key)


def _fernet_from_key(key: str | None) -> Fernet:
    if not key or not key.strip():
        raise SecretCryptoError("USER_SECRET_ENCRYPTION_KEY chưa được cấu hình.")
    try:
        return Fernet(key.strip().encode("ascii"))
    except Exception as error:
        raise SecretCryptoError("USER_SECRET_ENCRYPTION_KEY không hợp lệ.") from error
