# For local development, point SMTP_* vars at a local mail catcher
# e.g. Mailpit: docker run -p 1025:1025 -p 8025:8025 axllent/mailpit
# SMTP_HOST=localhost, SMTP_PORT=1025, SMTP_USERNAME="", SMTP_PASSWORD="", SMTP_FROM=noreply@voteme.local
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    async def send_confirmation_email(self, to: str, token: str) -> None:
        confirmation_url = f"{settings.frontend_url}/auth/confirm-email?token={token}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Confirm your VoteMe account"
        msg["From"] = settings.smtp_from
        msg["To"] = to

        text_body = f"Please confirm your email by visiting:\n{confirmation_url}"
        html_body = (
            f"<p>Please confirm your VoteMe account by clicking the link below:</p>"
            f'<p><a href="{confirmation_url}">Confirm email</a></p>'
            f"<p>Or copy this URL: {confirmation_url}</p>"
        )
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username or None,
                password=settings.smtp_password or None,
                start_tls=settings.smtp_start_tls,
                use_tls=settings.smtp_use_tls,
            )
            logger.info("Confirmation email sent to %s", to)
        except Exception as exc:
            logger.error("Failed to send confirmation email to %s: %s", to, exc)
            raise
