"""SMTP email service for the standalone auth system.

Separate from the existing Resend-based email.py to avoid coupling.
Uses aiosmtplib for async SMTP delivery.
Falls back to stdout logging when SMTP_HOST is not configured (dev mode).
"""
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.config import settings

log = logging.getLogger(__name__)


_VERIFY_HTML = """\
<!doctype html>
<html>
<body style="font-family:sans-serif;max-width:520px;margin:40px auto;color:#1a202c">
  <h2 style="color:#6366f1">Confirm your email</h2>
  <p>Click the button below to verify your email address and activate your account.</p>
  <a href="{link}"
     style="display:inline-block;margin:16px 0;padding:12px 24px;background:#6366f1;
            color:#fff;text-decoration:none;border-radius:8px;font-weight:600">
    Verify email
  </a>
  <p style="font-size:13px;color:#718096">
    This link expires in 24 hours.<br>
    If you didn't create an account, ignore this email.
  </p>
</body>
</html>
"""

_RESET_HTML = """\
<!doctype html>
<html>
<body style="font-family:sans-serif;max-width:520px;margin:40px auto;color:#1a202c">
  <h2 style="color:#6366f1">Reset your password</h2>
  <p>We received a request to reset the password for your account.</p>
  <a href="{link}"
     style="display:inline-block;margin:16px 0;padding:12px 24px;background:#6366f1;
            color:#fff;text-decoration:none;border-radius:8px;font-weight:600">
    Reset password
  </a>
  <p style="font-size:13px;color:#718096">
    This link expires in 1 hour.<br>
    If you didn't request a reset, ignore this email.
  </p>
</body>
</html>
"""


def _build_message(to: str, subject: str, html: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


async def _send(to: str, subject: str, html: str) -> None:
    if not settings.SMTP_HOST:
        log.info("DEV EMAIL | to=%s | subject=%s\n%s", to, subject, html)
        return

    msg = _build_message(to, subject, html)
    kwargs: dict = {
        "hostname": settings.SMTP_HOST,
        "port": settings.SMTP_PORT,
    }
    if settings.SMTP_USER:
        kwargs["username"] = settings.SMTP_USER
    if settings.SMTP_PASSWORD:
        kwargs["password"] = settings.SMTP_PASSWORD
    if settings.SMTP_PORT == 465:
        kwargs["use_tls"] = True
    elif settings.SMTP_PORT == 587:
        kwargs["start_tls"] = True

    await aiosmtplib.send(msg, **kwargs)
    log.info("Auth email sent | to=%s | subject=%s", to, subject)


async def send_verification_email(to: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/auth/verify-email?token={token}"
    await _send(to, "Verify your email — Varuflow", _VERIFY_HTML.format(link=link))


async def send_password_reset_email(to: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/auth/reset-password?token={token}"
    await _send(to, "Reset your password — Varuflow", _RESET_HTML.format(link=link))
