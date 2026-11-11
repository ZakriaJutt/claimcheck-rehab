"""B2 object storage against the local MinIO (S3 API, bucket claimcheck-dev): the minimised payload of a
completed import is stored under the clinic's prefix, downloaded only by that clinic, refused to another,
never stored for a refused import, removed by retention and by clinic deletion. Rows are synthetic; every
object a test creates is deleted at the end of the test."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text

from claimcheck_core.intake.contract import CLAIM_KEYS, VISIT_KEYS
from claimcheck_core.models import AuditEvent, ImportBatch
from claimcheck_core.payloads import delete_clinic_objects, purge_payloads
from claimcheck_core.storage import ClinicObjects, clinic_prefix, get_store
from claimcheck_core.tenancy import tenant_session
from tests.fixtures.synthetic import harbourview as hv_rows
from tests.integration.conftest import ClinicCtx, as_user, drain, upload

ENDPOINT = os.environ.get("S3_ENDPOINT_URL", "")


def _minio_up() -> bool:
    try:
        return bool(ENDPOINT) and httpx.get(f"{ENDPOINT}/minio/health/live", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(not _minio_up(), reason="MinIO not running on 127.0.0.1:9000")


@pytest.fixture(autouse=True)
def _cleanup(harbourview: ClinicCtx, seawall: ClinicCtx) -> Iterator[None]:
    yield
    for ctx in (harbourview, seawall):
        delete_clinic_objects(get_store(), ctx.id)
    assert get_store().list_keys(clinic_prefix(harbourview.id)) == []


def _small(prefix: str = "HV") -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows = hv_rows(prefix=prefix)
    return rows.visits[:9], rows.claims[:3]


def _batch(engine: Engine, ctx: ClinicCtx, bid: str) -> ImportBatch:
    with tenant_session(engine, ctx.id) as s:
        b = s.get(ImportBatch, uuid.UUID(bid))
        assert b is not None
        return b


def test_b2_payload_stored_under_clinic_prefix_and_downloaded_by_its_clinic_only(
        api: TestClient, harbourview: ClinicCtx, seawall: ClinicCtx, app_engine: Engine,
        owner_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    visits, claims = _small()
    bid, r = upload(api, harbourview, visits, claims)
    assert r.status_code == 202, r.text
    drain(monkeypatch)
    b = _batch(app_engine, harbourview, bid)
    assert b.status == "completed"
    assert b.payload_object_key == f"clinic/{harbourview.id}/jane_export/import_payload/{bid}.json"
    assert get_store().list_keys(clinic_prefix(harbourview.id)) == [b.payload_object_key]

    as_user(api, harbourview)
    r = api.get(f"/api/v1/imports/{bid}/payload")
    assert r.status_code == 200 and r.headers["content-type"] == "application/json"
    assert r.headers["cache-control"] == "no-store" and "attachment" in r.headers["content-disposition"]
    doc = r.json()
    assert len(doc["visits"]) == 9 and len(doc["claims"]) == 3
    # only the contract's 16 fields and the two ordinals were ever stored
    assert all(set(v) <= VISIT_KEYS for v in doc["visits"]) and all(set(c) <= CLAIM_KEYS for c in doc["claims"])
    assert set(doc) == {"format", "batch_id", "export_date", "content_hash", "visits", "claims"}

    # another clinic: 404 from the API, with an audit event; refused by its store binding too
    as_user(api, seawall)
    assert api.get(f"/api/v1/imports/{bid}/payload").status_code == 404
    with tenant_session(app_engine, seawall.id) as s:
        assert s.scalars(select(AuditEvent).where(AuditEvent.action == "cross_clinic_denied",
                                                   AuditEvent.object_id == uuid.UUID(bid))).first() is not None
    with pytest.raises(PermissionError):
        ClinicObjects(get_store(), seawall.id).get(b.payload_object_key)
    # no public URL: an unsigned request to the object is refused by the store
    anon = httpx.get(f"{ENDPOINT}/{os.environ['S3_BUCKET']}/{b.payload_object_key}", timeout=5)
    assert anon.status_code == 403
    # without a session there is no download at all
    api.cookies.clear()
    assert api.get(f"/api/v1/imports/{bid}/payload").status_code == 401


def test_b2_refused_import_stores_nothing(api: TestClient, harbourview: ClinicCtx, app_engine: Engine,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    visits, claims = _small()
    visits = [dict(v) for v in visits]
    for v in visits:
        v["invoice_ref"] = "Smith"  # a surname where the invoice number belongs: guard refuses the request
    bid, r = upload(api, harbourview, visits, claims)
    assert r.status_code == 422
    drain(monkeypatch)
    assert _batch(app_engine, harbourview, bid).payload_object_key is None
    assert get_store().list_keys(clinic_prefix(harbourview.id)) == []


def test_b2_retention_purge_and_clinic_deletion(api: TestClient, harbourview: ClinicCtx, seawall: ClinicCtx,
                                                app_engine: Engine, owner_engine: Engine,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    v1, c1 = _small("HA")
    b1, r = upload(api, harbourview, v1, c1, export_date="2026-11-02")
    assert r.status_code == 202
    drain(monkeypatch)
    v2, c2 = _small("HB")
    b2, r = upload(api, harbourview, v2, c2, export_date="2026-11-09")
    assert r.status_code == 202
    drain(monkeypatch)
    v3, c3 = _small("SW")
    b3, r = upload(api, seawall, v3, c3)
    assert r.status_code == 202
    drain(monkeypatch)
    now = datetime.now(tz=UTC)
    # Inside 24 hours nothing is purged.
    assert purge_payloads(app_engine, get_store(), harbourview.id, now) == 0
    with owner_engine.begin() as c:
        c.execute(text("UPDATE import_batch SET completed_at = now() - interval '25 hours' WHERE id = :b"),
                  {"b": b1})
    assert purge_payloads(app_engine, get_store(), harbourview.id, now) == 1
    first = _batch(app_engine, harbourview, b1)
    assert first.payload_deleted_at is not None
    assert get_store().list_keys(clinic_prefix(harbourview.id)) == [_batch(app_engine, harbourview, b2)
                                                                     .payload_object_key]
    as_user(api, harbourview)
    r = api.get(f"/api/v1/imports/{b1}/payload")
    assert r.status_code == 404 and r.json()["code"] == "payload_not_kept"
    # The latest completed batch with refused rows is kept past 24 hours (schema.md section 9).
    with owner_engine.begin() as c:
        c.execute(text("UPDATE import_batch SET completed_at = now() - interval '24 hours 30 minutes', "
                       "status = 'completed_with_rejects', rows_duplicate = 0 WHERE id = :b"), {"b": b2})
    assert purge_payloads(app_engine, get_store(), harbourview.id, now + timedelta(minutes=1)) == 0
    # Clinic deletion removes every object of that clinic and nothing of another.
    assert delete_clinic_objects(get_store(), harbourview.id) == 1
    assert get_store().list_keys(clinic_prefix(harbourview.id)) == []
    assert len(get_store().list_keys(clinic_prefix(seawall.id))) == 1
    assert json.loads(ClinicObjects(get_store(), seawall.id).get(
        _batch(app_engine, seawall, b3).payload_object_key or ""))["batch_id"] == b3
