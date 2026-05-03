"""Tạo lại email_preview.html ở root repo từ auth_email_html (cùng nguồn với email gửi đi)."""

from __future__ import annotations

import html
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.email_template import auth_email_html  # noqa: E402


def _srcdoc_attr(doc: str) -> str:
    return html.escape(doc, quote=True)


def main() -> None:
    logo_url = "https://example.com/logo.svg"
    verify_doc = auth_email_html(
        title="Xác minh email của bạn",
        eyebrow="AI Math Renderer",
        intro="Nhập mã OTP bên dưới hoặc mở liên kết xác minh để hoàn tất đăng ký tài khoản.",
        action_label="Xác minh email",
        action_url="https://example.com/verify-email?token=verify-preview-token",
        otp="123456",
        token="verify-preview-token",
        footer="Nếu bạn không tạo tài khoản AI Math Renderer, hãy bỏ qua email này.",
        logo_url=logo_url,
    )
    reset_token = "reset-preview-token-9qW4f7L2mP8xR1sT6vB3nY0cA5dE"
    reset_doc = auth_email_html(
        title="Đặt lại mật khẩu",
        eyebrow="Bảo mật tài khoản",
        intro="Bạn vừa yêu cầu đặt lại mật khẩu. Mở liên kết bên dưới hoặc dùng token để tiếp tục.",
        action_label="Đặt lại mật khẩu",
        action_url=f"https://example.com/reset-password?token={reset_token}",
        token=reset_token,
        footer="Nếu bạn không yêu cầu đặt lại mật khẩu, tài khoản của bạn vẫn an toàn và bạn có thể bỏ qua email này.",
        otp=None,
        logo_url=logo_url,
    )

    v_esc = _srcdoc_attr(verify_doc)
    r_esc = _srcdoc_attr(reset_doc)

    page = f"""<!doctype html>
<html lang="vi">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Email HTML review</title>
    <style>
      body {{ margin: 0; background: #f4f4f5; color: #18181b; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; }}
      .review-shell {{ max-width: 1320px; margin: 0 auto; padding: 32px 20px 56px; }}
      .review-header {{ margin: 0 0 24px; }}
      .review-header h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: -0.03em; }}
      .review-header p {{ margin: 0; color: #71717a; }}
      .review-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; align-items: start; }}
      .review-panel {{ border: 1px solid #d4d4d8; border-radius: 18px; background: #fff; overflow: hidden; box-shadow: 0 12px 28px rgba(0,0,0,.08); }}
      .review-panel h2 {{ margin: 0; padding: 16px 18px; border-bottom: 1px solid #e4e4e7; font-size: 16px; background: #fafafa; }}
      iframe {{ display: block; width: 100%; height: 860px; border: 0; background: #fafafa; }}
      @media (max-width: 1000px) {{ .review-grid {{ grid-template-columns: 1fr; }} iframe {{ height: 900px; }} }}
    </style>
  </head>
  <body>
    <main class="review-shell">
      <header class="review-header">
        <h1>Email HTML review</h1>
        <p>Preview lấy trực tiếp từ <code>auth_email_html</code> (backend). Chạy <code>python backend/scripts/generate_email_preview.py</code> sau khi sửa template.</p>
      </header>
      <section class="review-grid">
        <article class="review-panel">
          <h2>Email xác thực tài khoản</h2>
          <iframe title="Email xác thực tài khoản" srcdoc="{v_esc}"></iframe>
        </article>
        <article class="review-panel">
          <h2>Email quên mật khẩu</h2>
          <iframe title="Email quên mật khẩu" srcdoc="{r_esc}"></iframe>
        </article>
      </section>
    </main>
  </body>
</html>
"""
    out_path = REPO_ROOT / "email_preview.html"
    out_path.write_text(page, encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
