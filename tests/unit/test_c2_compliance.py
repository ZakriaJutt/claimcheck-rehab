"""C2 (2026-11-11): rules from compliance/self-check.md that change software behaviour.

Section 1 (CASL): every email names the sender with a mailing address and a contact (CASL s. 6(2)(a)-(b);
CRTC Regulations SOR/2012-36 s. 2(1)); a message that may be commercial carries an unsubscribe line
(CASL ss. 6(2)(c), 11); staging and production refuse to start without the address and contact.
"""

from __future__ import annotations

from claimcheck_core.mail import invite_mail, reset_mail, sender_footer
from tests.unit.test_foundation import _run

PROD = {"APP_ENV": "production", "DATABASE_URL": "postgresql://x@localhost/none",
        "PUBLIC_BASE_URL": "https://app.claimcheck.example", "S3_BUCKET": "claimcheck-prod",
        "S3_SERVER_SIDE_ENCRYPTION": "aws:kms",
        "TOTP_ENCRYPTION_KEY": "dGVzdC1vbmx5LXRvdHAta2V5LTMyLWJ5dGVzLWxvbmc="}
SENDER = {"MAIL_POSTAL_ADDRESS": "100 Example St, Vancouver BC", "MAIL_CONTACT": "privacy@claimcheck.example"}


def test_invitation_carries_sender_identification_and_unsubscribe() -> None:
    body = invite_mail("owner@example.test", "tok_abcdefghijklmnopqrstuvwxyz", 72).body
    assert "Sent by ClaimCheck Rehab" in body and "Contact:" in body
    assert "STOP" in body and "10 business days" in body
    assert body.index("#token=") < body.index("Sent by")


def test_reset_carries_identification_without_unsubscribe() -> None:
    body = reset_mail("staff@example.test", "tok_abcdefghijklmnopqrstuvwxyz", 30).body
    assert "Sent by ClaimCheck Rehab" in body
    assert "STOP" not in body


def test_footer_uses_configured_values_and_carries_no_row_data() -> None:
    code = "from claimcheck_core.mail import sender_footer; print(sender_footer(True))"
    r = _run(code, {**PROD, **SENDER, "MAIL_SENDER_NAME": "ClaimCheck Rehab"})
    assert r.returncode == 0, r.stderr
    assert "100 Example St, Vancouver BC" in r.stdout and "write STOP to privacy@claimcheck.example" in r.stdout
    local = sender_footer(False)
    assert "invoice" not in local.lower() and "$" not in local


def test_production_refuses_to_start_without_casl_sender_details() -> None:
    r = _run("from claimcheck_core.settings import load_settings; load_settings()", PROD)
    assert r.returncode == 2 and "MAIL_POSTAL_ADDRESS" in r.stderr
    r = _run("from claimcheck_core.settings import load_settings; load_settings()",
             {**PROD, "MAIL_POSTAL_ADDRESS": "100 Example St, Vancouver BC"})
    assert r.returncode == 2 and "MAIL_CONTACT" in r.stderr
    r = _run("from claimcheck_core.settings import load_settings; load_settings(); print('ok')",
             {**PROD, **SENDER})
    assert r.returncode == 0, r.stderr
