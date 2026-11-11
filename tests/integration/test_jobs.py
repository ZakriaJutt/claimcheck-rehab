"""UT-13 stale lease; two workers claim one job; IT-10 worker killed during finalize."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text

from claimcheck_core.jobs import claim_next, complete, enqueue, expire_leases
from claimcheck_core.models import ImportBatch, Visit, VisitSnapshot
from claimcheck_core.tenancy import tenant_session
from tests.conftest import ROOT
from tests.fixtures.synthetic import harbourview as hv_rows
from tests.integration.conftest import ClinicCtx, drain, upload


def _job(engine: Engine, ctx: ClinicCtx, key: str) -> None:
    with tenant_session(engine, ctx.id) as s:
        enqueue(s, ctx.id, "staleness_check", key)


def test_ut13_completion_with_stale_lease_updates_nothing(app_engine: Engine, owner_engine: Engine,
                                                          worker_engine: Engine,
                                                          harbourview: ClinicCtx,
                                                          caplog: pytest.LogCaptureFixture) -> None:
    _job(app_engine, harbourview, "k1")
    job = claim_next(worker_engine, 60)
    assert job is not None and job.attempt == 1
    assert complete(worker_engine, job.id, uuid.uuid4(), ok=True) == 0  # someone else's lease
    with owner_engine.connect() as c:
        assert c.execute(text("SELECT status FROM job WHERE id = :i"), {"i": job.id}).scalar() == "running"
    assert complete(worker_engine, job.id, job.lease_token, ok=True) == 1
    assert complete(worker_engine, job.id, job.lease_token, ok=True) == 0  # duplicate completion
    with owner_engine.connect() as c:
        assert c.execute(text("SELECT status FROM job WHERE id = :i"), {"i": job.id}).scalar() == "succeeded"


def test_two_workers_claim_one_job(app_engine: Engine, worker_engine: Engine, harbourview: ClinicCtx) -> None:
    _job(app_engine, harbourview, "k2")
    first = claim_next(worker_engine, 60)
    second = claim_next(worker_engine, 60)
    assert first is not None and second is None


def test_enqueue_is_idempotent_and_retry_backs_off(app_engine: Engine, owner_engine: Engine, worker_engine: Engine,
                                                   harbourview: ClinicCtx) -> None:
    _job(app_engine, harbourview, "k3")
    _job(app_engine, harbourview, "k3")
    with owner_engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM job WHERE idempotency_key='k3'")).scalar() == 1
    job = claim_next(worker_engine, 60)
    assert job is not None
    complete(worker_engine, job.id, job.lease_token, ok=False, error_code="Boom")
    with owner_engine.connect() as c:
        row = c.execute(text("SELECT status, run_after > now(), last_error_code FROM job WHERE id=:i"),
                        {"i": job.id}).one()
    assert tuple(row) == ("queued", True, "Boom")


def test_it10_worker_killed_during_finalize_retry_completes_without_duplicates(
        api: TestClient, harbourview: ClinicCtx, app_engine: Engine, owner_engine: Engine,
        worker_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = hv_rows()
    bid, r = upload(api, harbourview, rows.visits, rows.claims)
    assert r.status_code == 202
    env = {**os.environ, "CLAIMCHECK_TEST_PAUSE_FINALIZE_S": "60", "PYTHONPATH": str(ROOT),
           "DATABASE_URL": os.environ["TEST_WORKER_DATABASE_URL"]}
    proc = subprocess.Popen([sys.executable, "-m", "claimcheck_worker.main", "--once", "--no-schedule"],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            with owner_engine.connect() as c:
                st = c.execute(text("SELECT status FROM job WHERE kind='import_finalize'")).scalar()
            if st == "running":
                break
            time.sleep(0.2)
        assert st == "running"
        time.sleep(3)  # inside the pause: rows written but not committed
    finally:
        proc.send_signal(signal.SIGKILL)
        proc.wait(timeout=10)
    with tenant_session(app_engine, harbourview.id) as s:
        assert s.scalar(select(func.count()).select_from(Visit)) == 0  # the killed transaction left nothing
    with owner_engine.begin() as c:  # let the lease run out instead of waiting 120 s
        c.execute(text("UPDATE job SET lease_expires_at = now() - interval '1 second' WHERE status='running'"))
    assert expire_leases(worker_engine) == 1
    drain(monkeypatch)
    with tenant_session(app_engine, harbourview.id) as s:
        b = s.get(ImportBatch, bid)
        assert b is not None and b.status == "completed"
        assert s.scalar(select(func.count()).select_from(Visit)) == 1184
        assert s.scalar(select(func.count()).select_from(VisitSnapshot)) == 1184
    with owner_engine.connect() as c:
        st, attempt = c.execute(text("SELECT status, attempt FROM job WHERE kind='import_finalize'")).one()
    assert (st, attempt) == ("succeeded", 2)
    # a repeat of the finalize after success is a no-op
    from claimcheck_core.imports import finalize
    from tests.integration.conftest import TODAY
    assert finalize(app_engine, harbourview.id, uuid.UUID(bid), TODAY) == "completed"


def test_b1_008_api_role_cannot_run_queue_functions(app_engine: Engine, harbourview: ClinicCtx,
                                                     seawall: ClinicCtx) -> None:
    """Regression for reviewer case A14: the API role must not claim another clinic's job."""
    from sqlalchemy.exc import ProgrammingError
    _job(app_engine, harbourview, "k-a14")
    for sql in ("SELECT * FROM cc_job_claim(gen_random_uuid(), 60, NULL)", "SELECT cc_job_expire_leases()",
                "SELECT cc_job_complete(gen_random_uuid(), gen_random_uuid(), true, NULL, true)",
                "SELECT cc_enqueue_per_clinic('x', 'y', '{}'::jsonb, gen_random_uuid())"):
        with pytest.raises(ProgrammingError), tenant_session(app_engine, seawall.id) as s:
            s.execute(text(sql))
