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
    # Logo SVG thật từ frontend/img.svg - simplified version cho email
    logo_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="96" height="96">
      <defs>
        <filter id="core-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="8" result="blur1" />
          <feMerge>
            <feMergeNode in="blur1" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <linearGradient id="prism-top" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#00F2FE" stop-opacity="0.9" />
          <stop offset="100%" stop-color="#4FACFE" stop-opacity="0.6" />
        </linearGradient>
        <linearGradient id="prism-right" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#FF0844" stop-opacity="0.9" />
          <stop offset="100%" stop-color="#FFB199" stop-opacity="0.6" />
        </linearGradient>
        <linearGradient id="prism-left" x1="100%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#B224EF" stop-opacity="0.9" />
          <stop offset="100%" stop-color="#7579FF" stop-opacity="0.6" />
        </linearGradient>
      </defs>
      <g transform="translate(256, 256)">
        <circle cx="0" cy="0" r="220" fill="none" stroke="#e5e5e5" stroke-width="1" stroke-dasharray="4 8" opacity="0.3" />
        <ellipse cx="0" cy="0" rx="190" ry="60" fill="none" stroke="#00F2FE" stroke-width="1.5" stroke-dasharray="12 6" transform="rotate(-30)" opacity="0.6" />
        <g filter="url(#core-glow)">
          <polygon points="0,-90 77.94,-45 0,0 -77.94,-45" fill="url(#prism-top)" stroke="#00F2FE" stroke-width="1.5" />
          <polygon points="0,0 77.94,-45 77.94,45 0,90" fill="url(#prism-right)" stroke="#FFB199" stroke-width="1.5" />
          <polygon points="0,0 0,90 -77.94,45 -77.94,-45" fill="url(#prism-left)" stroke="#B224EF" stroke-width="1.5" />
        </g>
        <polyline points="0,-90 0,0" fill="none" stroke="#FFFFFF" stroke-width="2.5" opacity="0.9" />
        <polyline points="-77.94,-45 0,0 77.94,-45" fill="none" stroke="#FFFFFF" stroke-width="2.5" opacity="0.7" />
        <path d="M 0,-40 C 6,-12 12,-6 40,0 C 12,6 6,12 0,40 C -6,12 -12,6 -40,0 C -12,-6 -6,-12 0,-40 Z" fill="#FFFFFF" filter="url(#core-glow)" />
        <circle cx="0" cy="0" r="5" fill="#FFFFFF" />
      </g>
    </svg>'''

    otp_block = ""
    if otp:
        otp_digits = "".join(f'<span class="otp-digit">{escape(digit)}</span>' for digit in otp)
        copy_icon = '''<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="5" y="5" width="9" height="9" rx="1.5" stroke="currentColor" stroke-width="1.5" fill="none"/>
          <path d="M3 10.5V3.5C3 2.67 3.67 2 4.5 2H10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/>
        </svg>'''
        otp_block = f'''
          <div class="otp-section">
            <div class="section-label">Mã xác minh</div>
            <div class="otp-container">
              <div class="otp-display">{otp_digits}</div>
              <button class="copy-button" onclick="navigator.clipboard.writeText('{escape(otp)}')" title="Sao chép mã">{copy_icon}</button>
            </div>
            <p class="hint-text">Mã này có hiệu lực trong 24 giờ. Không chia sẻ với bất kỳ ai.</p>
          </div>
        '''

    return f'''
<!doctype html>
<html lang="vi">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="color-scheme" content="light dark" />
    <meta name="supported-color-schemes" content="light dark" />
    <style>
      :root {{
        color-scheme: light dark;
        supported-color-schemes: light dark;
      }}
      body {{
        margin: 0;
        padding: 0;
        background: #fafafa;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
      }}
      .email-wrapper {{
        max-width: 600px;
        margin: 0 auto;
        padding: 40px 20px;
      }}
      .email-card {{
        background: #ffffff;
        border: 1px solid #e5e5e5;
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
      }}
      .email-header {{
        padding: 32px 32px 24px;
        background: linear-gradient(135deg, #171717 0%, #262626 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 16px;
      }}
      .logo-container {{
        margin: 0;
        width: 132px;
        height: 132px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
      }}
      .logo-container svg {{
        width: 132px;
        height: 132px;
      }}
      .eyebrow {{
        display: inline-block;
        margin: 0;
        padding: 8px 16px;
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.15);
        color: #e5e5e5;
        font-size: 18px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}
      .email-body {{
        padding: 32px;
      }}
      .email-title {{
        margin: 0 0 12px;
        color: #171717;
        font-size: 28px;
        font-weight: 700;
        line-height: 1.2;
        letter-spacing: -0.02em;
      }}
      .email-intro {{
        margin: 0 0 28px;
        color: #525252;
        font-size: 16px;
        line-height: 1.6;
      }}
      .cta-button {{
        display: inline-block;
        margin: 0 0 32px;
        padding: 14px 28px;
        border-radius: 10px;
        background: #171717;
        color: #ffffff !important;
        text-decoration: none;
        font-size: 16px;
        font-weight: 600;
        text-align: center;
        transition: background 0.2s;
      }}
      .cta-button:hover {{
        background: #262626;
      }}
      .otp-section {{
        margin: 0 0 28px;
        padding: 24px;
        border: 1px solid #e5e5e5;
        border-radius: 12px;
        background: #fafafa;
      }}
      .section-label {{
        margin: 0 0 12px;
        color: #737373;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}
      .otp-container {{
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 0 0 12px;
      }}
      .otp-display {{
        display: flex;
        gap: 8px;
        flex: 1;
      }}
      .otp-digit {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 48px;
        height: 56px;
        border: 2px solid #d4d4d4;
        border-radius: 10px;
        background: #ffffff;
        color: #171717;
        font-size: 28px;
        font-weight: 700;
        font-variant-numeric: tabular-nums;
        user-select: all;
      }}
      .copy-button {{
        padding: 10px 12px;
        border: 1px solid #d4d4d4;
        border-radius: 8px;
        background: #ffffff;
        color: #171717;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        white-space: nowrap;
        display: inline-flex;
        align-items: center;
        justify-content: center;
      }}
      .copy-button:hover {{
        background: #f5f5f5;
        border-color: #a3a3a3;
      }}
      .copy-button svg {{
        display: block;
      }}
      .hint-text {{
        margin: 0;
        color: #737373;
        font-size: 13px;
        line-height: 1.5;
      }}
      .email-footer {{
        padding: 24px 32px;
        border-top: 1px solid #e5e5e5;
        background: #fafafa;
      }}
      .footer-text {{
        margin: 0 0 8px;
        color: #737373;
        font-size: 13px;
        line-height: 1.6;
      }}
      .footer-text:last-child {{
        margin: 0;
      }}
      .footer-brand {{
        color: #171717;
        font-weight: 600;
      }}
      @media (max-width: 600px) {{
        .email-wrapper {{ padding: 20px 12px; }}
        .email-header {{ padding: 24px 20px 20px; }}
        .email-header {{ gap: 12px; }}
        .logo-container, .logo-container svg {{ width: 96px; height: 96px; }}
        .eyebrow {{ font-size: 14px; padding: 6px 12px; }}
        .email-body {{ padding: 24px 20px; }}
        .email-title {{ font-size: 24px; }}
        .otp-digit {{ width: 40px; height: 48px; font-size: 24px; }}
        .otp-container {{ flex-direction: column; align-items: stretch; }}
        .copy-button {{ width: 100%; }}
      }}
      @media (prefers-color-scheme: dark) {{
        body {{ background: #0a0a0a; }}
        .email-card {{ background: #171717; border-color: #262626; }}
        .email-body {{ background: #171717; }}
        .email-title {{ color: #fafafa; }}
        .email-intro {{ color: #a3a3a3; }}
        .cta-button {{ background: #fafafa; color: #171717 !important; }}
        .cta-button:hover {{ background: #e5e5e5; }}
        .otp-section {{ background: #0a0a0a; border-color: #262626; }}
        .section-label {{ color: #a3a3a3; }}
        .otp-digit {{ background: #171717; border-color: #404040; color: #fafafa; }}
        .copy-button {{ background: #262626; border-color: #404040; color: #fafafa; }}
        .copy-button:hover {{ background: #404040; }}
        .copy-button svg {{ color: #fafafa; }}
        .hint-text {{ color: #a3a3a3; }}
        .email-footer {{ background: #0a0a0a; border-color: #262626; }}
        .footer-text {{ color: #a3a3a3; }}
        .footer-brand {{ color: #fafafa; }}
      }}
    </style>
  </head>
  <body>
    <div class="email-wrapper">
      <div class="email-card">
        <div class="email-header">
          <div class="logo-container">{logo_svg}</div>
          <span class="eyebrow">{escape(eyebrow)}</span>
        </div>
        <div class="email-body">
          <h2 class="email-title">{escape(title)}</h2>
          <p class="email-intro">{escape(intro)}</p>
          <a class="cta-button" href="{escape(action_url, quote=True)}">{escape(action_label)}</a>
          {otp_block}
        </div>
        <div class="email-footer">
          <p class="footer-text">{escape(footer)}</p>
          <p class="footer-text"><span class="footer-brand">Hinh Math Renderer</span> · Email tự động, vui lòng không trả lời.</p>
        </div>
      </div>
    </div>
  </body>
</html>
'''.strip()
