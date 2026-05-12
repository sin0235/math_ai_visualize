import json
import logging
from functools import lru_cache

from fastapi import HTTPException, status

from app.core.config import Settings

logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import auth as firebase_admin_auth
    from firebase_admin import credentials
except ImportError:  # pragma: no cover - exercised only when optional dependency is absent.
    firebase_admin = None
    firebase_admin_auth = None
    credentials = None


@lru_cache(maxsize=1)
def _initialize_firebase_app(project_id: str | None, credentials_json: str | None, credentials_path: str | None) -> object:
    if firebase_admin is None or firebase_admin_auth is None:
        raise RuntimeError("firebase-admin chưa được cài đặt trên backend.")
    if firebase_admin._apps:
        return firebase_admin.get_app()

    options = {"projectId": project_id} if project_id else None
    if credentials_json:
        cert = credentials.Certificate(json.loads(credentials_json))
        return firebase_admin.initialize_app(cert, options)
    if credentials_path:
        cert = credentials.Certificate(credentials_path)
        return firebase_admin.initialize_app(cert, options)
    return firebase_admin.initialize_app(options=options)


def firebase_auth_enabled(settings: Settings) -> bool:
    return bool(settings.firebase_project_id or settings.firebase_credentials_json or settings.firebase_credentials_path)


async def verify_firebase_id_token(id_token: str, settings: Settings) -> dict:
    if not firebase_auth_enabled(settings):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Firebase Auth chưa được cấu hình trên backend.")
    try:
        _initialize_firebase_app(settings.firebase_project_id, settings.firebase_credentials_json, settings.firebase_credentials_path)
        return firebase_admin_auth.verify_id_token(id_token, check_revoked=True)
    except HTTPException:
        raise
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except Exception as error:
        logger.warning("Firebase token verification failed: %s: %s", type(error).__name__, error)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firebase token không hợp lệ hoặc đã hết hạn.") from error
