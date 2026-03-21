"""Email sending utility. Uses SMTP when configured, otherwise logs the message."""

import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@cloudfire.one")


def is_email_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASS)


def send_email(to: str, subject: str, html_body: str) -> bool:
    if not is_email_configured():
        logger.warning("SMTP not configured. Email not sent to %s: %s", to, subject)
        logger.info("Email body:\n%s", html_body)
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = FROM_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, to, msg.as_string())
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def send_password_reset_email(to: str, reset_url: str) -> bool:
    subject = "Cloudfire - Password Reset"
    html = f"""\
<div style="font-family: 'DM Sans', Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 24px;">
  <div style="text-align: center; margin-bottom: 24px;">
    <h1 style="font-family: 'Space Grotesk', Arial, sans-serif; font-size: 24px; margin: 0;">
      <span style="color: #FF6B35;">Cloud</span><span style="color: #FFD166;">fire</span>
    </h1>
  </div>
  <div style="background: #fff; border: 3px solid #000; box-shadow: 6px 6px 0 #000; border-radius: 6px; padding: 32px 24px;">
    <h2 style="margin: 0 0 16px; font-size: 20px;">Reset your password</h2>
    <p style="color: #555; font-size: 14px; line-height: 1.6;">
      We received a request to reset your password. Click the button below to choose a new one.
      This link expires in 1 hour.
    </p>
    <div style="text-align: center; margin: 28px 0;">
      <a href="{reset_url}"
         style="display: inline-block; background: #FF6B35; color: #fff; font-weight: bold;
                padding: 12px 32px; border: 3px solid #000; box-shadow: 4px 4px 0 #000;
                border-radius: 6px; text-decoration: none; font-size: 14px;">
        Reset Password
      </a>
    </div>
    <p style="color: #999; font-size: 12px; line-height: 1.5;">
      If you didn't request this, you can safely ignore this email. Your password won't change.
    </p>
  </div>
  <p style="text-align: center; color: #999; font-size: 11px; margin-top: 24px;">
    Cloudfire Image Generator
  </p>
</div>"""
    return send_email(to, subject, html)
