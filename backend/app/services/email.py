import logging
import smtplib
from email.message import EmailMessage
from html import escape
from urllib.parse import urlencode

import resend

from app.core.config import Settings
from app.db.models import UserRecord

logger = logging.getLogger(__name__)


async def send_verification_email(user: UserRecord, token: str, otp: str, settings: Settings) -> None:
    link = auth_link(settings, "verify-email", token)
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
    )
    await send_email(user.email, subject, text, html, settings)


async def send_password_reset_email(user: UserRecord, token: str, settings: Settings) -> None:
    link = auth_link(settings, "reset-password", token)
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


def auth_link(settings: Settings, auth_action: str, token: str) -> str:
    base_url = settings.public_app_url.rstrip("/") or "http://localhost:5173"
    return f"{base_url}/?{urlencode({'auth': auth_action, 'token': token})}"


def auth_email_html(
    *,
    title: str,
    eyebrow: str,
    intro: str,
    action_label: str,
    action_url: str,
    token: str,
    footer: str,
    otp: str | None = None,
) -> str:
    otp_block = ""
    if otp:
        otp_digits = "".join(f'<span class="otp-digit">{escape(digit)}</span>' for digit in otp)
        otp_block = f"""
          <div class="code-card">
            <div class="code-label">Mã OTP</div>
            <div class="otp">{otp_digits}</div>
            <p>Mã OTP dùng cùng liên kết xác minh và sẽ hết hạn sớm.</p>
          </div>
        """

    return f"""
<!doctype html>
<html lang="vi">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      body {{ margin:0; padding:0; background:#0a0a0a; color:#ffffff; font-family:Inter,Segoe UI,Roboto,Arial,sans-serif; }}
      .wrap {{ padding:32px 16px; }}
      .card {{ max-width:640px; margin:0 auto; background:#1a1a1a; border:1px solid #2a2a2a; border-radius:16px; overflow:hidden; box-shadow:0 24px 70px rgba(0,0,0,.5); }}
      .hero {{ padding:34px 34px 24px; background:linear-gradient(135deg,#000000,#1a1a1a); border-bottom:1px solid #2a2a2a; }}
      .logo {{ display:flex; align-items:center; gap:12px; margin-bottom:20px; }}
      .logo-icon {{ width:40px; height:40px; background:#ffffff; border-radius:8px; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:20px; color:#000000; }}
      .brand {{ font-size:13px; letter-spacing:.08em; text-transform:uppercase; color:#888888; }}
      h1 {{ margin:22px 0 10px; font-size:30px; line-height:1.12; color:#ffffff; }}
      .hero p {{ margin:0; color:#aaaaaa; font-size:16px; line-height:1.6; }}
      .body {{ padding:30px 34px 34px; }}
      .button {{ display:inline-block; margin:8px 0 24px; padding:14px 22px; border-radius:8px; background:#ffffff; color:#000000 !important; text-decoration:none; font-weight:700; transition:background .2s; }}
      .button:hover {{ background:#e5e5e5; }}
      .code-card {{ margin:0 0 22px; padding:20px; border-radius:12px; background:#0a0a0a; border:1px solid #2a2a2a; }}
      .code-label {{ color:#888888; font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:.08em; }}
      .otp {{ display:flex; gap:8px; margin:12px 0; }}
      .otp-digit {{ display:inline-flex; align-items:center; justify-content:center; width:42px; height:50px; border-radius:8px; background:#1a1a1a; border:1px solid #3a3a3a; font-size:24px; font-weight:800; color:#ffffff; }}
      .token {{ word-break:break-all; padding:14px; border-radius:8px; background:#0a0a0a; color:#cccccc; font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:13px; border:1px solid #2a2a2a; }}
      .muted {{ color:#888888; font-size:14px; line-height:1.6; }}
      .muted a {{ color:#aaaaaa; text-decoration:underline; }}
      .footer {{ padding-top:22px; border-top:1px solid #2a2a2a; }}
      @media (max-width:520px) {{ .hero,.body {{ padding-left:22px; padding-right:22px; }} .otp-digit {{ width:34px; height:44px; }} }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <main class="card">
        <section class="hero">
          <div class="logo">
            <div class="logo-icon">H</div>
            <div>
              <div style="font-weight:700;font-size:18px;color:#ffffff;">Hinh</div>
              <div class="brand">{escape(eyebrow)}</div>
            </div>
          </div>
          <h1>{escape(title)}</h1>
          <p>{escape(intro)}</p>
        </section>
        <section class="body">
          <a class="button" href="{escape(action_url, quote=True)}">{escape(action_label)}</a>
          {otp_block}
          <div class="code-card">
            <div class="code-label">Token dự phòng</div>
            <p class="muted">Nếu nút không mở được, hãy copy token này vào màn hình xác thực tương ứng.</p>
            <div class="token">{escape(token)}</div>
          </div>
          <p class="muted">Hoặc copy liên kết này vào trình duyệt:<br><a href="{escape(action_url, quote=True)}">{escape(action_url)}</a></p>
          <div class="footer">
            <p class="muted">{escape(footer)}</p>
            <p class="muted">Hinh Math Renderer · Email tự động, vui lòng không trả lời trực tiếp.</p>
          </div>
        </section>
      </main>
    </div>
  </body>
</html>
""".strip()
