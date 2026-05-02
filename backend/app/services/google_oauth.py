from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import Settings

GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


@dataclass(frozen=True)
class GoogleUserInfo:
    subject: str
    email: str
    email_verified: bool
    display_name: str | None = None
    picture_url: str | None = None


def google_oauth_configured(settings: Settings) -> bool:
    return bool(settings.google_oauth_client_id and settings.google_oauth_client_secret and settings.google_oauth_redirect_uri)


def build_google_authorization_url(settings: Settings, state: str) -> str:
    query = urlencode(
        {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    return f"{GOOGLE_AUTHORIZATION_URL}?{query}"


async def exchange_google_code(settings: Settings, code: str) -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
    response.raise_for_status()
    payload = response.json()
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise ValueError("Google token response thiếu access_token.")
    return access_token


async def fetch_google_userinfo(access_token: str) -> GoogleUserInfo:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
    response.raise_for_status()
    payload = response.json()
    subject = payload.get("sub")
    email = payload.get("email")
    email_verified = payload.get("email_verified")
    if not isinstance(subject, str) or not subject:
        raise ValueError("Google userinfo thiếu subject.")
    if not isinstance(email, str) or not email:
        raise ValueError("Google userinfo thiếu email.")
    return GoogleUserInfo(
        subject=subject,
        email=email,
        email_verified=email_verified is True or email_verified == "true",
        display_name=payload.get("name") if isinstance(payload.get("name"), str) else None,
        picture_url=payload.get("picture") if isinstance(payload.get("picture"), str) else None,
    )
