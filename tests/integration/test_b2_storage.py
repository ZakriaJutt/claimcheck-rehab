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
from sqlalchemy import Engine, func, select, text

from claimcheck_core.intake.contract import CLAIM_KEYS, VISIT_KEYS
from claimcheck_core.models import AuditEvent, ImportBatch, ImportRow
from claimcheck_core.payloads import delete_clinic_objects, purge_payloads, sweep_expired_objects
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
    # B2-S02 regression (reviewer S15b): no exception for the latest batch with refused rows; a 90-day-old
    # one is removed, and its refused rows stay listed from import_row in the database.
    with owner_engine.begin() as c:
        c.execute(text("UPDATE import_batch SET completed_at = now() - interval '90 days', "
                       "status = 'completed_with_rejects' WHERE id = :b"), {"b": b2})
    assert purge_payloads(app_engine, get_store(), harbourview.id, now) == 1
    assert get_store().list_keys(clinic_prefix(harbourview.id)) == []
    with tenant_session(app_engine, harbourview.id) as s:
        assert s.scalar(select(func.count()).select_from(ImportRow).where(ImportRow.batch_id == uuid.UUID(b2))) == 12
    # An orphan (object with no import_batch record) is removed once it is an hour old; a fresh one is not
    # (a commit may still be in flight).
    orphan = ClinicObjects(get_store(), harbourview.id).put("jane_export", "import_payload", uuid.uuid4(), b"{}")
    assert purge_payloads(app_engine, get_store(), harbourview.id, datetime.now(tz=UTC)) == 0
    assert purge_payloads(app_engine, get_store(), harbourview.id, datetime.now(tz=UTC) + timedelta(hours=2)) == 1
    assert orphan not in get_store().list_keys(clinic_prefix(harbourview.id))
    # An object older than 24 hours by its own timestamp goes even if its database row says otherwise.
    v4, c4 = _small("HC")
    b4, r = upload(api, harbourview, v4, c4, export_date="2026-11-10")
    assert r.status_code == 202
    drain(monkeypatch)
    assert purge_payloads(app_engine, get_store(), harbourview.id, datetime.now(tz=UTC) + timedelta(hours=25)) == 1
    assert _batch(app_engine, harbourview, b4).payload_deleted_at is not None
    # A fresh batch, for the deletion check below.
    v5, c5 = _small("HD")
    b5, r = upload(api, harbourview, v5, c5, export_date="2026-11-11")
    assert r.status_code == 202
    drain(monkeypatch)
    # Clinic deletion removes every object of that clinic and nothing of another.
    assert delete_clinic_objects(get_store(), harbourview.id) == 1
    assert get_store().list_keys(clinic_prefix(harbourview.id)) == []
    assert len(get_store().list_keys(clinic_prefix(seawall.id))) == 1
    assert json.loads(ClinicObjects(get_store(), seawall.id).get(
        _batch(app_engine, seawall, b3).payload_object_key or ""))["batch_id"] == b3
    # Last: the bucket-wide sweep removes expired payload objects of a clinic with no rows left (deleted clinic).
    ghost = ClinicObjects(get_store(), uuid.uuid4()).put("jane_export", "import_payload", uuid.uuid4(), b"{}")
    assert sweep_expired_objects(get_store(), datetime.now(tz=UTC)) == 0
    assert sweep_expired_objects(get_store(), datetime.now(tz=UTC) + timedelta(hours=25)) >= 1
    assert ghost not in get_store().list_keys("clinic/")


def test_b2_tampered_object_key_is_404_with_audit(api: TestClient, harbourview: ClinicCtx, seawall: ClinicCtx,
                                                  app_engine: Engine, owner_engine: Engine,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """B2-S04 regression (reviewer S13b): a batch row pointing at another clinic's key answers 404, is
    audited as cross-clinic, and returns nothing of the other clinic."""
    v, c = _small("TA")
    bid_a, r = upload(api, harbourview, v, c)
    v, c = _small("TB")
    bid_b, r2 = upload(api, seawall, v, c)
    assert r.status_code == r2.status_code == 202
    drain(monkeypatch)
    key_b = _batch(app_engine, seawall, bid_b).payload_object_key
    with owner_engine.begin() as conn:
        conn.execute(text("UPDATE import_batch SET payload_object_key = :k WHERE id = :b"), {"k": key_b, "b": bid_a})
    as_user(api, harbourview)
    r = api.get(f"/api/v1/imports/{bid_a}/payload")
    assert r.status_code == 404 and r.json()["code"] == "not_found" and bid_b not in r.text
    with tenant_session(app_engine, harbourview.id) as s:
        assert s.scalars(select(AuditEvent).where(AuditEvent.action == "cross_clinic_denied",
                                                   AuditEvent.object_id == uuid.UUID(bid_a))).first() is not None
    with pytest.raises(PermissionError):
        ClinicObjects(get_store(), harbourview.id).get(f"clinic/{harbourview.id}/../{seawall.id}/x.json")


def test_b2_objects_are_tagged_and_the_bucket_lifecycle_rule_is_set(
        api: TestClient, harbourview: ClinicCtx, app_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    """B2-S02: the backstop rule expires tagged payload objects after one day."""
    from scripts.setup_storage import RULE_ID, setup
    assert setup() is True
    client = get_store()._c  # type: ignore[attr-defined]
    rules = client.get_bucket_lifecycle_configuration(Bucket=os.environ["S3_BUCKET"])["Rules"]
    rule = next(x for x in rules if x["ID"] == RULE_ID)
    assert rule["Expiration"]["Days"] == 1 and rule["Status"] == "Enabled"
    assert rule["Filter"]["And"]["Tags"] == [{"Key": "purpose", "Value": "import_payload"}]
    v, c = _small()
    bid, r = upload(api, harbourview, v, c)
    assert r.status_code == 202
    drain(monkeypatch)
    key = _batch(app_engine, harbourview, bid).payload_object_key
    tags = client.get_object_tagging(Bucket=os.environ["S3_BUCKET"], Key=key)["TagSet"]
    assert {"Key": "purpose", "Value": "import_payload"} in tags
