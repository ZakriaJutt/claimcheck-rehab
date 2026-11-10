"""The one tenancy module (R-05). Only this module sets app.clinic_id.

Every clinic-owned table has a row-level-security policy comparing clinic_id with
current_setting('app.clinic_id'). The setting is transaction-local (SET LOCAL semantics), so it
cannot leak to the next request on a pooled connection. Without it, every policy returns zero rows.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session


@contextmanager
def tenant_session(engine: Engine, clinic_id: uuid.UUID) -> Iterator[Session]:
    """One transaction scoped to one clinic. Commits on success, rolls back on error."""
    if not isinstance(clinic_id, uuid.UUID):
        raise TypeError("clinic_id must be a UUID")
    with Session(engine, expire_on_commit=False) as session, session.begin():
        session.execute(text("SELECT set_config('app.clinic_id', :cid, true)"), {"cid": str(clinic_id)})
        yield session


@contextmanager
def system_session(engine: Engine) -> Iterator[Session]:
    """A transaction with no clinic context: clinic tables return zero rows. Used for the job queue
    functions (SECURITY DEFINER), session lookup and global tables (rule_version, export_profile)."""
    with Session(engine, expire_on_commit=False) as session, session.begin():
        session.execute(text("SELECT set_config('app.clinic_id', '', true)"))
        yield session


def current_clinic(session: Session) -> uuid.UUID | None:
    value = session.execute(text("SELECT nullif(current_setting('app.clinic_id', true), '')")).scalar()
    return uuid.UUID(value) if value else None
