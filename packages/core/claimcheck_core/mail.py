"""Email through SMTP only (B2). Locally the Mailpit inbox (127.0.0.1:1025, no authentication); a real
provider later through the same interface, selected by settings alone.

Messages carry links and counts only, never row data (AD-08). Links are built only from PUBLIC_BASE_URL
(R-16). Tokens go in the URL fragment, so they are not sent to any server in a request line or Referer.

C2 (compliance/self-check.md section 1): every message ends with the sender identification that CASL s. 6(2)
and CRTC Regulations SOR/2012-36 s. 2(1) require (name, mailing address, email or web contact); a message that
could be read as commercial (the invitation, and later the weekly email) also carries an unsubscribe line
(CASL s. 11). The values come from settings and are required in staging and production.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

from claimcheck_core.logging import get_logger, log_event
from claimcheck_core.settings import Settings, get_settings

_log = get_logger("mail")


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    body: str


class Mailer(Protocol):
    def send(self, mail: Mail) -> None: ...


class SmtpMailer:
    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def send(self, mail: Mail) -> None:
        msg = EmailMessage()
        msg["From"] = self._s.smtp_from
        msg["To"] = mail.to
        msg["Subject"] = mail.subject
        msg.set_content(mail.body)
        with smtplib.SMTP(self._s.smtp_host, self._s.smtp_port, timeout=self._s.smtp_timeout_seconds) as smtp:
            if self._s.smtp_starttls:
                smtp.starttls()
            if self._s.smtp_username and self._s.smtp_password:
                smtp.login(self._s.smtp_username, self._s.smtp_password)
            smtp.send_message(msg)


@dataclass
class MemoryMailer:
    """Test double: keeps messages in memory."""

    sent: list[Mail] = field(default_factory=list)

    def send(self, mail: Mail) -> None:
        self.sent.append(mail)


def get_mailer() -> Mailer:
    return SmtpMailer(get_settings())


def link(path: str, token: str) -> str:
    return f"{get_settings().public_base_url}{path}#token={token}"


def sender_footer(unsubscribe: bool) -> str:
    """CASL identification (and, for a possibly commercial message, the unsubscribe line). No row data."""
    s = get_settings()
    name = s.mail_sender_name.strip() or "ClaimCheck Rehab"
    address = s.mail_postal_address.strip() or "[mailing address not set]"
    contact = s.mail_contact.strip() or "[contact not set]"
    text = f"\n--\nSent by {name}, {address}. Contact: {contact}.\n"
    if unsubscribe:
        text += (f"To stop receiving messages from {name}, write STOP to {contact}; it takes effect within "
                 "10 business days.\n")
    return text


def invite_mail(to: str, token: str, hours: int) -> Mail:
    return Mail(to, "You are invited to ClaimCheck Rehab",
                f"Your clinic has invited you to ClaimCheck Rehab.\n\nSet your password and authenticator app here "
                f"(the link works once and expires in {hours} hours):\n{link('/invite', token)}\n\n"
                "If you did not expect this, ignore this message.\n" + sender_footer(unsubscribe=True))


def reset_mail(to: str, token: str, minutes: int) -> Mail:
    return Mail(to, "Reset your ClaimCheck Rehab password",
                f"Someone asked to reset the password for this address.\n\nChoose a new password here (the link "
                f"works once and expires in {minutes} minutes):\n{link('/reset', token)}\n\nYou will still need "
                "your authenticator code to sign in. If you did not ask, ignore this message.\n"
                + sender_footer(unsubscribe=False))


def send_safely(mailer: Mailer, mail: Mail, kind: str) -> bool:
    """Send; on failure log the kind and error type only (never the address or the link)."""
    try:
        mailer.send(mail)
    except (OSError, smtplib.SMTPException) as exc:
        log_event(_log, "mail_failed", 40, kind=kind, error_type=type(exc).__name__)
        return False
    log_event(_log, "mail_sent", kind=kind)
    return True
