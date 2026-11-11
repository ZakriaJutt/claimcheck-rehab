"""Integration fixtures: schema reset and migration once per session, synthetic clinics per test."""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from tests.conftest import ROOT

TODAY = date(2026, 11, 10)
CLINIC_TABLES = ("audit_event", "item_event", "item", "finding", "evaluation_run", "visit_snapshot", "visit",
                 "claim", "import_row", "import_batch", "job", "session", "app_user", "clinic")


def reset_and_migrate(owner_url: str) -> None:
    eng = create_engine(owner_url, isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    eng.dispose()
    env = {**os.environ, "MIGRATION_DATABASE_URL": owner_url}
    subprocess.run([sys.executable, "-m", "alembic", "-c", str(ROOT / "packages/core/alembic.ini"), "upgrade",
                    "head"], check=True, env=env, capture_output=True)
    eng = create_engine(owner_url)
    from claimcheck_core.seed import publish_profiles, publish_rules
    with eng.begin() as c:
        publish_profiles(c)
        publish_rules(c, fixtures_passed=True)  # the rule unit tests run in the same suite
    eng.dispose()


@pytest.fixture(scope="session")
def owner_engine() -> Iterator[Engine]:
    url = os.environ.get("TEST_MIGRATION_DATABASE_URL")
    if not url:
        pytest.skip("TEST_MIGRATION_DATABASE_URL not set")
    reset_and_migrate(url)
    eng = create_engine(url)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def app_engine(owner_engine: Engine) -> Iterator[Engine]:
    from claimcheck_core.db import get_engine
    eng = get_engine()
    with eng.connect() as c:
        role = c.execute(text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")).scalar()
    assert role is False, "application tests must run as a role without superuser or BYPASSRLS"
    yield eng


@pytest.fixture(scope="session")
def worker_engine(owner_engine: Engine) -> Iterator[Engine]:
    """The worker's own role (B1-008): the only role that may run the cross-clinic queue functions."""
    url = os.environ.get("TEST_WORKER_DATABASE_URL")
    if not url:
        pytest.skip("TEST_WORKER_DATABASE_URL not set")
    eng = create_engine(url)
    with eng.connect() as c:
        assert c.execute(text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
                         ).scalar() is False
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def _clean(request: pytest.FixtureRequest) -> None:
    if "owner_engine" not in request.fixturenames and "app_engine" not in request.fixturenames:
        return
    eng: Engine = request.getfixturevalue("owner_engine")
    with eng.begin() as c:
        c.execute(text("TRUNCATE " + ", ".join(CLINIC_TABLES) + " CASCADE"))


@dataclass
class ClinicCtx:
    id: uuid.UUID
    owner_id: uuid.UUID
    staff_id: uuid.UUID
    owner_token: str
    staff_token: str
    csrf: str


def make_clinic(owner_engine: Engine, name: str) -> ClinicCtx:
    cid, oid, sid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    otok, stok, csrf = secrets.token_urlsafe(16), secrets.token_urlsafe(16), secrets.token_urlsafe(16)
    from claimcheck_api.deps import hash_token
    now = datetime.now(tz=UTC)
    with owner_engine.begin() as c:
        c.execute(text("INSERT INTO clinic (id, name, location_label, payers, status) "
                       "VALUES (:id, :n, 'Main', ARRAY['ICBC','WSBC'], 'pilot')"), {"id": cid, "n": name})
        for uid, role in ((oid, "owner"), (sid, "staff")):
            c.execute(text("INSERT INTO app_user (id, clinic_id, email, password_hash, role) "
                           "VALUES (:u, :c, :e, 'not-a-real-hash', :r)"),
                      {"u": uid, "c": cid, "e": f"{role}.{cid.hex[:8]}@example.test", "r": role})
        for uid, tok in ((oid, otok), (sid, stok)):
            c.execute(text("INSERT INTO session (user_id, token_hash, mfa_passed, last_seen_at, expires_at) "
                           "VALUES (:u, :h, true, :n, :x)"),
                      {"u": uid, "h": hash_token(tok), "n": now, "x": now + timedelta(hours=12)})
    return ClinicCtx(cid, oid, sid, otok, stok, csrf)


@pytest.fixture
def harbourview(owner_engine: Engine) -> ClinicCtx:
    return make_clinic(owner_engine, "Harbourview Physio")


@pytest.fixture
def seawall(owner_engine: Engine) -> ClinicCtx:
    return make_clinic(owner_engine, "Seawall Rehab")


@pytest.fixture
def api(app_engine: Engine) -> Iterator[TestClient]:
    from claimcheck_api.deps import today_dep
    from claimcheck_api.main import create_app
    app = create_app()
    app.dependency_overrides[today_dep] = lambda: TODAY
    with TestClient(app) as client:
        yield client


def as_user(client: TestClient, ctx: ClinicCtx, role: str = "staff") -> dict[str, str]:
    client.cookies.clear()
    client.cookies.set("cc_session", ctx.staff_token if role == "staff" else ctx.owner_token)
    client.cookies.set("cc_csrf", ctx.csrf)
    return {"X-CSRF-Token": ctx.csrf}


def drain(monkeypatch: pytest.MonkeyPatch, on: date = TODAY, max_jobs: int = 50) -> int:
    """Run due jobs in-process the way the worker does (as the worker role), with a fixed local date."""
    import claimcheck_worker.main as worker
    eng = create_engine(os.environ["TEST_WORKER_DATABASE_URL"])
    monkeypatch.setattr(worker, "local_today", lambda: on)
    monkeypatch.setattr(worker, "get_engine", lambda: eng)
    n = 0
    while n < max_jobs and worker.process_one():
        n += 1
    return n


def upload(client: TestClient, ctx: ClinicCtx, visits: list[dict[str, Any]], claims: list[dict[str, Any]],
           export_date: str = "2026-11-09", content_hash: str | None = None) -> tuple[str, Any]:
    """Drive the browser's three calls: create batch, rows in batches of 500, finalize."""
    import hashlib
    import json
    headers = as_user(client, ctx)
    digest = content_hash or hashlib.sha256(json.dumps([visits, claims, export_date], sort_keys=True,
                                                       default=str).encode()).hexdigest()
    r = client.post("/api/v1/imports", json={"export_date": export_date, "profile_sales_version": 1,
                                             "profile_policies_version": 1},
                    headers={**headers, "Idempotency-Key": digest})
    assert r.status_code in (200, 201), r.text
    bid = r.json()["id"]
    if r.json()["status"] != "receiving":
        return bid, r
    for i in range(0, max(len(visits), 1), 500):
        chunk = {"visits": visits[i:i + 500]}
        if i == 0:
            chunk["claims"] = []
        r = client.post(f"/api/v1/imports/{bid}/rows", json=chunk, headers=headers)
        if r.status_code != 200:
            return bid, r
    for i in range(0, len(claims), 500):
        r = client.post(f"/api/v1/imports/{bid}/rows", json={"claims": claims[i:i + 500]}, headers=headers)
        if r.status_code != 200:
            return bid, r
    r = client.post(f"/api/v1/imports/{bid}/finalize", json={"expected_rows": len(visits) + len(claims)},
                    headers=headers)
    return bid, r
