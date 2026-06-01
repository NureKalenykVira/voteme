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

    async def send_password_reset_email(self, to: str, token: str) -> None:
        reset_url = f"{settings.frontend_url}/auth/reset-password?token={token}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Reset your VoteMe password"
        msg["From"] = settings.smtp_from
        msg["To"] = to

        text_body = f"Reset your VoteMe password by visiting:\n{reset_url}\n\nThis link expires in 1 hour."
        html_body = (
            f"<p>You requested a password reset for your VoteMe account.</p>"
            f'<p><a href="{reset_url}">Reset password</a></p>'
            f"<p>Or copy this URL: {reset_url}</p>"
            f"<p>This link expires in 1 hour. If you did not request a reset, ignore this email.</p>"
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
            logger.info("Password reset email sent to %s", to)
        except Exception as exc:
            logger.error("Failed to send password reset email to %s: %s", to, exc)
            raise

    async def send_voter_invitation_email(
        self, to: str, election_title: str, join_link: str
    ) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"You've been invited to vote in: {election_title}"
        msg["From"] = settings.smtp_from
        msg["To"] = to

        text_body = (
            f"You've been invited to vote in: {election_title}\n"
            f"Join the election here:\n{join_link}"
        )
        html_body = (
            f"<p>You've been invited to vote in: <strong>{election_title}</strong></p>"
            f'<p><a href="{join_link}">Join the election</a></p>'
            f"<p>Or copy this URL: {join_link}</p>"
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
            logger.info("Voter invitation email sent to %s", to)
        except Exception as exc:
            logger.error("Failed to send voter invitation email to %s: %s", to, exc)

    async def send_voter_removed_email(
        self, to: str, election_title: str
    ) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"You've been removed from the voter list for: {election_title}"
        msg["From"] = settings.smtp_from
        msg["To"] = to

        text_body = (
            f"You've been removed from the voter list for: {election_title}.\n"
            f"If you believe this was a mistake, please contact the election organizer."
        )
        html_body = (
            f"<p>You've been removed from the voter list for: <strong>{election_title}</strong>.</p>"
            f"<p>If you believe this was a mistake, please contact the election organizer.</p>"
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
            logger.info("Voter removal email sent to %s", to)
        except Exception as exc:
            logger.error("Failed to send voter removal email to %s: %s", to, exc)

    async def send_auditor_invitation_email(
        self, to: str, election_title: str, event_log_url: str
    ) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"You've been appointed as auditor for: {election_title}"
        msg["From"] = settings.smtp_from
        msg["To"] = to

        text_body = (
            f"You've been appointed as an auditor for the election: {election_title}\n"
            f"You can now view the event log at:\n{event_log_url}"
        )
        html_body = (
            f"<p>You've been appointed as an auditor for: <strong>{election_title}</strong></p>"
            f'<p><a href="{event_log_url}">View the event log</a></p>'
            f"<p>Or copy this URL: {event_log_url}</p>"
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
            logger.info("Auditor invitation email sent to %s", to)
        except Exception as exc:
            logger.error("Failed to send auditor invitation email to %s: %s", to, exc)
