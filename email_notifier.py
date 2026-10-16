"""
Email notification module — sends HTML-formatted reports via Gmail SMTP.
"""

import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from config import EmailConfig

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Send email alerts through Gmail SMTP with retry logic."""

    def __init__(self, config: Optional[EmailConfig] = None) -> None:
        self.cfg = config or EmailConfig()

    def send(self, subject: str, html_body: str) -> bool:
        """
        Send an HTML email.  Returns True on success, False on failure.

        Retries up to ``cfg.max_retries`` times on transient errors.
        """
        if not self.cfg.is_configured():
            logger.error(
                "Email not configured — set EMAIL_ADDRESS, EMAIL_PASSWORD, "
                "and RECIPIENT_EMAIL environment variables."
            )
            return False

        msg = self._build_message(subject, html_body)

        for attempt in range(1, self.cfg.max_retries + 1):
            try:
                logger.info(
                    "Sending email (attempt %d/%d) to %s …",
                    attempt,
                    self.cfg.max_retries,
                    self.cfg.recipient_email,
                )
                with smtplib.SMTP(self.cfg.smtp_server, self.cfg.smtp_port) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(self.cfg.sender_email, self.cfg.sender_password)
                    server.sendmail(
                        self.cfg.sender_email,
                        self.cfg.recipient_email,
                        msg.as_string(),
                    )
                logger.info("✅ Email sent successfully.")
                return True

            except smtplib.SMTPAuthenticationError as exc:
                logger.error(
                    "Authentication failed — check your Gmail App Password: %s", exc
                )
                return False  # no point retrying auth errors

            except (smtplib.SMTPException, OSError) as exc:
                logger.warning(
                    "Email attempt %d failed: %s", attempt, exc
                )
                if attempt < self.cfg.max_retries:
                    time.sleep(self.cfg.retry_delay_seconds)

        logger.error("All %d email attempts failed.", self.cfg.max_retries)
        return False

    # ── helpers ──────────────────────────────────────────────────────────

    def _build_message(self, subject: str, html_body: str) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.cfg.sender_email
        msg["To"] = self.cfg.recipient_email

        # Plain-text fallback
        text_fallback = (
            "Your ETF analysis report is ready. "
            "Please view this email in an HTML-capable client."
        )
        msg.attach(MIMEText(text_fallback, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        return msg
