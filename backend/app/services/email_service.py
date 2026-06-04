import asyncio
import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.config import settings

logger = logging.getLogger(__name__)


def _email_html(title: str, body_html: str, cta_label: str | None = None, cta_url: str | None = None, fallback_url: str | None = None) -> str:
    cta_block = ""
    if cta_label and cta_url:
        cta_block = f"""
        <tr><td style="padding:32px 0 12px;text-align:center;">
          <a href="{cta_url}" style="display:inline-block;background:#c8f135;color:#1a1a1a;font-weight:700;font-size:17px;text-decoration:none;padding:16px 48px;border-radius:999px;">{cta_label}</a>
        </td></tr>"""
    fallback_block = ""
    if fallback_url:
        fallback_block = f"""
        <tr><td style="padding:8px 0 0;text-align:center;font-size:12px;color:#888;">
          Or copy this link: <a href="{fallback_url}" style="color:#5b4fe8;word-break:break-all;">{fallback_url}</a>
        </td></tr>"""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;">
    <tr><td>
      <table width="100%" cellpadding="0" cellspacing="0">
        <!-- Header -->
        <tr><td style="background:#5b4fe8;padding:28px 40px 32px;">
          <p style="margin:0 0 12px 0;color:rgba(255,255,255,0.7);font-size:13px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;">VoteMe</p>
          <p style="margin:0;color:#ffffff;font-size:26px;font-weight:800;line-height:1.2;">{title}</p>
        </td></tr>
        <!-- Body -->
        <tr><td style="background:#ffffff;padding:32px 40px;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr><td style="font-size:15px;color:#444;line-height:1.7;">{body_html}</td></tr>
            {cta_block}
            {fallback_block}
          </table>
        </td></tr>
        <!-- Footer -->
        <tr><td style="background:#f4f4f8;padding:20px 40px;text-align:center;font-size:12px;color:#999;">
          © VoteMe · Transparent Electronic Voting
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _send_via_gmail_api(msg: MIMEMultipart) -> None:
    creds = Credentials(
        token=None,
        refresh_token=settings.gmail_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret,
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )
    creds.refresh(Request())
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


class EmailService:
    async def _send_message(self, msg: MIMEMultipart, raise_on_error: bool = True) -> None:
        try:
            if settings.gmail_refresh_token:
                await asyncio.to_thread(_send_via_gmail_api, msg)
            else:
                await aiosmtplib.send(
                    msg,
                    hostname=settings.smtp_host,
                    port=settings.smtp_port,
                    username=settings.smtp_username or None,
                    password=settings.smtp_password or None,
                    start_tls=settings.smtp_start_tls,
                    use_tls=settings.smtp_use_tls,
                )
        except Exception as exc:
            logger.error("Failed to send email to %s: %s", msg["To"], exc)
            if raise_on_error:
                raise

    async def send_confirmation_email(self, to: str, token: str) -> None:
        confirmation_url = f"{settings.frontend_url}/auth/confirm-email?token={token}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Confirm your VoteMe account"
        msg["From"] = settings.smtp_from
        msg["To"] = to

        text_body = f"Please confirm your email by visiting:\n{confirmation_url}"
        html_body = _email_html(
            title="Confirm your email",
            body_html="<p>Welcome to VoteMe! Please confirm your email address to activate your account.</p>",
            cta_label="Confirm email",
            cta_url=confirmation_url,
            fallback_url=confirmation_url,
        )
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        await self._send_message(msg, raise_on_error=True)
        logger.info("Confirmation email sent to %s", to)

    async def send_password_reset_email(self, to: str, token: str) -> None:
        reset_url = f"{settings.frontend_url}/auth/reset-password?token={token}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Reset your VoteMe password"
        msg["From"] = settings.smtp_from
        msg["To"] = to

        text_body = f"Reset your VoteMe password by visiting:\n{reset_url}\n\nThis link expires in 1 hour."
        html_body = _email_html(
            title="Reset your password",
            body_html="<p>You requested a password reset for your VoteMe account.</p><p>This link expires in <strong>1 hour</strong>. If you did not request a reset, ignore this email.</p>",
            cta_label="Reset password",
            cta_url=reset_url,
            fallback_url=reset_url,
        )
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        await self._send_message(msg, raise_on_error=True)
        logger.info("Password reset email sent to %s", to)

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
        html_body = _email_html(
            title="You've been invited to vote",
            body_html=f"<p>You've been invited to participate in the election:</p><p><strong>{election_title}</strong></p>",
            cta_label="Join the election",
            cta_url=join_link,
            fallback_url=join_link,
        )
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        await self._send_message(msg, raise_on_error=False)
        logger.info("Voter invitation email sent to %s", to)

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
        html_body = _email_html(
            title="Voter list update",
            body_html=f"<p>You've been removed from the voter list for:</p><p><strong>{election_title}</strong></p><p style='color:#888;font-size:13px;'>If you believe this was a mistake, please contact the election organizer.</p>",
        )
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        await self._send_message(msg, raise_on_error=False)
        logger.info("Voter removal email sent to %s", to)

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
        html_body = _email_html(
            title="You've been appointed as auditor",
            body_html=f"<p>You've been granted auditor access for the election:</p><p><strong>{election_title}</strong></p>",
            cta_label="View event log",
            cta_url=event_log_url,
            fallback_url=event_log_url,
        )
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        await self._send_message(msg, raise_on_error=False)
        logger.info("Auditor invitation email sent to %s", to)

    async def send_results_email(
        self, to: str, election_title: str, results_url: str
    ) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Results are in: {election_title}"
        msg["From"] = settings.smtp_from
        msg["To"] = to

        text_body = (
            f"The results for '{election_title}' are now available.\n"
            f"View results: {results_url}"
        )
        html_body = _email_html(
            title="Results are in!",
            body_html=f"<p>The voting has concluded and results for <strong>{election_title}</strong> are now available.</p>",
            cta_label="View results",
            cta_url=results_url,
            fallback_url=results_url,
        )
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        await self._send_message(msg, raise_on_error=False)
        logger.info("Results email sent to %s", to)

    async def send_election_started_email(
        self, to: str, election_title: str, join_link: str
    ) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Voting has started: {election_title}"
        msg["From"] = settings.smtp_from
        msg["To"] = to

        text_body = (
            f"The voting '{election_title}' has started!\n"
            f"Cast your vote here: {join_link}"
        )
        html_body = _email_html(
            title="Voting has started!",
            body_html=f"<p>The election <strong>{election_title}</strong> is now open for voting.</p><p>Don't miss your chance to participate!</p>",
            cta_label="Cast your vote",
            cta_url=join_link,
            fallback_url=join_link,
        )
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        await self._send_message(msg, raise_on_error=False)
        logger.info("Election started email sent to %s", to)
