"""Operator: create a clinic (or use an existing one) and email its first owner an invitation (B2).

The invitation goes through SMTP (locally the Mailpit inbox at http://127.0.0.1:8025); the token is never
printed. The clinic row is created with the migration connection, because the application role cannot
create clinics; the invitation is written through the application role under the clinic's row-level
security, as the API does. Synthetic names and @example.test addresses only, locally.

Usage: python scripts/invite_owner.py --email owner@example.test [--clinic-name "Harbourview Physio"]
       [--clinic-id UUID]
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid

from sqlalchemy import create_engine, text

from claimcheck_core.auth.service import create_invite
from claimcheck_core.db import get_engine
from claimcheck_core.mail import get_mailer, invite_mail, send_safely
from claimcheck_core.settings import get_settings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="invite_owner")
    p.add_argument("--email", required=True)
    p.add_argument("--clinic-name")
    p.add_argument("--clinic-id", type=uuid.UUID)
    args = p.parse_args(argv)
    if not args.clinic_id and not args.clinic_name:
        print("give --clinic-name or --clinic-id", file=sys.stderr)
        return 2
    clinic_id = args.clinic_id
    if clinic_id is None:
        owner = create_engine(os.environ["MIGRATION_DATABASE_URL"])
        with owner.begin() as c:
            clinic_id = c.execute(text(
                "INSERT INTO clinic (name, location_label, payers, status) "
                "VALUES (:n, 'Main', ARRAY['ICBC','WSBC'], 'onboarding') RETURNING id"), {"n": args.clinic_name}
            ).scalar_one()
        owner.dispose()
    invite_id, token, _ = create_invite(get_engine(), clinic_id, args.email, "owner", None)
    sent = send_safely(get_mailer(), invite_mail(args.email, token, get_settings().invite_hours), "invite")
    print(f"clinic {clinic_id}; invitation {invite_id}; email {'sent' if sent else 'NOT sent'}")
    return 0 if sent else 1


if __name__ == "__main__":
    raise SystemExit(main())
