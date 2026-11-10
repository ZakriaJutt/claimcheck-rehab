"""Daily identifier_scan job: re-runs the guard's checks over a clinic's stored rows; a match alerts the
operator and pauses imports for the clinic until reviewed (TRD jobs table; IT-18)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Engine, select

from claimcheck_core.alerts import Alerter, default_alerter
from claimcheck_core.intake.guard import GuardFailure, check_rows
from claimcheck_core.models import Claim, Clinic, Visit
from claimcheck_core.tenancy import tenant_session


def identifier_scan(engine: Engine, clinic_id: uuid.UUID, today: date,
                    alerter: Alerter = default_alerter) -> list[GuardFailure]:
    with tenant_session(engine, clinic_id) as s:
        visits = [{"invoice_ref": v.invoice_ref, "date_of_service": v.date_of_service, "state_date": v.state_date}
                  for v in s.scalars(select(Visit))]
        claims = [{"end_date": c.end_date, "next_appointment_date": c.next_appointment_date,
                   "date_of_event": c.date_of_event} for c in s.scalars(select(Claim))]
        # Stored history legitimately ages past three years only after retention would have removed it.
        failures = check_rows(visits, claims, today)
        if failures:
            clinic = s.get(Clinic, clinic_id)
            if clinic is not None and clinic.imports_paused_at is None:
                clinic.imports_paused_at = datetime.now(tz=UTC)
            alerter.alert(s, "identifier_scan_match", clinic_id, checks=len(failures),
                          rows=sum(f.rows for f in failures))
        return failures
