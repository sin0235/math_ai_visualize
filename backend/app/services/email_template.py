from html import escape
from urllib.parse import urlencode

from app.core.config import Settings


def auth_link(settings: Settings, auth_action: str, token: str) -> str:
    base_url = settings.public_app_url.rstrip("/") or "http://localhost:5173"
    return f"{base_url}/{auth_action}?{urlencode({'token': token})}"


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
    logo_url: str | None = None,
) -> str:
    logo_markup = ""
    if logo_url:
        logo_markup = f'''
          <tr>
            <td align="center" style="padding:0 0 12px 0;">
              <img src="{escape(logo_url, quote=True)}" width="96" height="96" alt="AI Math Renderer" style="display:block;width:96px;height:96px;border:0;outline:none;text-decoration:none;" />
            </td>
          </tr>
        '''

    otp_block = ""
    if otp:
        otp_digits = "".join(
            f'<td align="center" style="padding:0 4px;"><span style="display:inline-block;width:42px;padding:12px 0;border:2px solid #d4d4d4;border-radius:10px;background:#ffffff;color:#171717;font-size:26px;font-weight:700;line-height:1;text-align:center;font-family:Arial,sans-serif;">{escape(digit)}</span></td>'
            for digit in otp
        )
        otp_block = f'''
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 28px 0;border:1px solid #e5e5e5;border-radius:12px;background:#fafafa;">
            <tr>
              <td style="padding:22px 20px;">
                <p style="margin:0 0 12px 0;color:#737373;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;font-family:Arial,sans-serif;">Mã xác minh</p>
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 12px 0;">
                  <tr>{otp_digits}</tr>
                </table>
                <p style="margin:0;color:#737373;font-size:13px;line-height:1.5;font-family:Arial,sans-serif;">Mã này có hiệu lực trong 24 giờ. Không chia sẻ với bất kỳ ai.</p>
              </td>
            </tr>
          </table>
        '''
    else:
        escaped_token = escape(token)
        otp_block = f'''
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 28px 0;border:1px solid #e5e5e5;border-radius:12px;background:#fafafa;">
            <tr>
              <td style="padding:22px 20px;">
                <p style="margin:0 0 12px 0;color:#737373;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;font-family:Arial,sans-serif;">Token đặt lại mật khẩu</p>
                <div style="padding:14px 16px;border:2px solid #d4d4d4;border-radius:10px;background:#ffffff;color:#171717;font-family:Consolas,'Liberation Mono',monospace;font-size:14px;font-weight:600;line-height:1.5;word-break:break-all;">{escaped_token}</div>
                <p style="margin:12px 0 0 0;color:#737373;font-size:13px;line-height:1.5;font-family:Arial,sans-serif;">Token này chỉ dùng để đặt lại mật khẩu và sẽ hết hạn sớm. Không chia sẻ với bất kỳ ai.</p>
              </td>
            </tr>
          </table>
        '''

    escaped_title = escape(title)
    escaped_intro = escape(intro)
    escaped_eyebrow = escape(eyebrow)
    escaped_action_label = escape(action_label)
    escaped_action_url = escape(action_url, quote=True)
    escaped_footer = escape(footer)

    return f'''
<!doctype html>
<html lang="vi">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="color-scheme" content="light" />
    <meta name="supported-color-schemes" content="light" />
    <title>{escaped_title}</title>
  </head>
  <body style="margin:0;padding:0;background:#fafafa;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#fafafa;border-collapse:collapse;">
      <tr>
        <td align="center" style="padding:40px 16px;">
          <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;border-collapse:separate;border-spacing:0;background:#ffffff;border:1px solid #e5e5e5;border-radius:16px;overflow:hidden;">
            <tr>
              <td align="center" style="padding:32px 32px 24px 32px;background:#171717;background-image:linear-gradient(135deg,#171717 0%,#262626 100%);">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;">
                  {logo_markup}
                  <tr>
                    <td align="center">
                      <span style="display:inline-block;padding:8px 16px;border-radius:6px;background:#3a3a3a;color:#e5e5e5;font-family:Arial,sans-serif;font-size:15px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;">{escaped_eyebrow}</span>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:32px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">
                <h1 style="margin:0 0 12px 0;color:#171717;font-size:28px;font-weight:700;line-height:1.2;letter-spacing:-.02em;">{escaped_title}</h1>
                <p style="margin:0 0 28px 0;color:#525252;font-size:16px;line-height:1.6;">{escaped_intro}</p>
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 32px 0;border-collapse:collapse;">
                  <tr>
                    <td align="center" bgcolor="#171717" style="border-radius:10px;">
                      <a href="{escaped_action_url}" style="display:inline-block;padding:14px 28px;border-radius:10px;background:#171717;color:#ffffff;text-decoration:none;font-size:16px;font-weight:700;font-family:Arial,sans-serif;">{escaped_action_label}</a>
                    </td>
                  </tr>
                </table>
                {otp_block}
              </td>
            </tr>
            <tr>
              <td style="padding:24px 32px;border-top:1px solid #e5e5e5;background:#fafafa;font-family:Arial,sans-serif;">
                <p style="margin:0 0 8px 0;color:#737373;font-size:13px;line-height:1.6;">{escaped_footer}</p>
                <p style="margin:0;color:#737373;font-size:13px;line-height:1.6;"><strong style="color:#171717;">AI Math Renderer</strong> · Email tự động, vui lòng không trả lời.</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
'''.strip()
