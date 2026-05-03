import logging
import smtplib
from email.message import EmailMessage

import resend

from app.core.config import Settings
from app.db.models import UserRecord
from app.services.email_template import auth_email_html, auth_link

logger = logging.getLogger(__name__)


def email_logo_url(settings: Settings) -> str:
    base_url = settings.public_app_url.rstrip("/") or "http://localhost:5173"
    return f"{base_url}/logo.svg"


async def send_verification_email(user: UserRecord, token: str, otp: str, settings: Settings) -> None:
    link = auth_link(settings, "verify-email", token)
    logo_url = email_logo_url(settings)
    subject = "Xác minh email tài khoản Hinh"
    text = (
        "Mở liên kết này để xác minh email tài khoản Hinh:\n"
        f"{link}\n\n"
        f"Mã OTP của bạn là: {otp}\n\n"
        "Liên kết và mã OTP sẽ hết hạn sớm. Không chia sẻ mã này với bất kỳ ai."
    )
    html = auth_email_html(
        title="Xác minh email của bạn",
        eyebrow="AI Math Renderer",
        intro="Nhập mã OTP bên dưới hoặc mở liên kết xác minh để hoàn tất đăng ký tài khoản.",
        action_label="Xác minh email",
        action_url=link,
        otp=otp,
        token=token,
        footer="Nếu bạn không tạo tài khoản AI Math Renderer, hãy bỏ qua email này.",
        logo_url=logo_url,
    )
    await send_email(user.email, subject, text, html, settings)


async def send_password_reset_email(user: UserRecord, token: str, settings: Settings) -> None:
    link = auth_link(settings, "reset-password", token)
    logo_url = email_logo_url(settings)
    subject = "Đặt lại mật khẩu Hinh"
    text = (
        "Mở liên kết này để đặt lại mật khẩu tài khoản Hinh:\n"
        f"{link}\n\n"
        f"Token đặt lại mật khẩu: {token}\n\n"
        "Liên kết sẽ hết hạn sớm. Nếu bạn không yêu cầu đặt lại mật khẩu, hãy bỏ qua email này."
    )
    html = auth_email_html(
        title="Đặt lại mật khẩu",
        eyebrow="Bảo mật tài khoản",
        intro="Bạn vừa yêu cầu đặt lại mật khẩu. Mở liên kết bên dưới hoặc dùng token để tiếp tục.",
        action_label="Đặt lại mật khẩu",
        action_url=link,
        token=token,
        footer="Nếu bạn không yêu cầu đặt lại mật khẩu, tài khoản của bạn vẫn an toàn và bạn có thể bỏ qua email này.",
        logo_url=logo_url,
    )
    await send_email(user.email, subject, text, html, settings)


async def send_email(to_email: str, subject: str, text: str, html: str, settings: Settings) -> None:
    from_email = settings.resend_from_email or settings.smtp_from_email
    if settings.resend_api_key:
        resend.api_key = settings.resend_api_key
        try:
            resend.Emails.send(
                {
                    "from": from_email,
                    "to": [to_email],
                    "subject": subject,
                    "html": html,
                    "text": text,
                }
            )
            return
        except Exception:
            logger.exception("Resend email delivery failed to=%s subject=%s", to_email, subject)
            if not settings.smtp_host:
                raise

    if not settings.smtp_host:
        if settings.auth_email_dev_mode:
            logger.warning("Auth email dev mode to=%s subject=%s body=%s", to_email, subject, text)
        return

    message = EmailMessage()
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
