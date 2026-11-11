"""The minimised import payload in the object store (B2, AD-11).

After a batch completes, the worker writes the rows exactly as the browser sent them (the 16 fields and
two ordinals; nothing else ever reaches the server) as one JSON object under the clinic's prefix.
Guard-rejected and failed batches store nothing.

Retention (B2-S02 ruling): an object lives at most 24 hours, with no exception. The list of refused rows of
the latest batch is read from `import_row` in PostgreSQL, never from the object. Three layers enforce it:
(1) `purge_payloads`, run per clinic at least hourly, removes every object whose batch completed more than
24 hours ago, every object older than 24 hours by its own timestamp, and every object with no
`import_batch` record (an orphan left when a commit failed after the write) once it is an hour old;
(2) `sweep_expired_objects`, run hourly by the worker over the whole bucket, removes payload objects older
than 24 hours even for clinics that no longer exist; (3) the bucket lifecycle rule set by
`scripts/setup_storage.py` expires tagged objects after one day if the worker is not running.
Clinic deletion removes every object under the clinic's prefix.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, select

from claimcheck_core.audit import write_audit
from claimcheck_core.models import ImportBatch, ImportRow
from claimcheck_core.storage import BlobStore, ClinicObjects
from claimcheck_core.tenancy import tenant_session

SOURCE = "jane_export"
PURPOSE = "import_payload"
RETENTION = timedelta(hours=24)
ORPHAN_GRACE = timedelta(hours=1)  # an object written moments ago may belong to a commit still in flight
DONE = ("completed", "completed_with_rejects")


def archive_payload(engine: Engine, store: BlobStore, clinic_id: uuid.UUID, batch_id: uuid.UUID) -> str | None:
    """Idempotent: a batch already archived (or not completed) is left alone. Returns the key written."""
    with tenant_session(engine, clinic_id) as s:
        batch = s.get(ImportBatch, batch_id, with_for_update=True)
        if batch is None or batch.status not in DONE or batch.payload_object_key or batch.payload_deleted_at:
            return None
        if batch.completed_at is not None and batch.completed_at < datetime.now(tz=UTC) - RETENTION:
            return None  # a job retried late must not store rows that are already past their retention
        rows = list(s.scalars(select(ImportRow).where(ImportRow.batch_id == batch_id)
                              .order_by(ImportRow.kind, ImportRow.row_no)))
        doc = {
            "format": "claimcheck.import_payload.v1",
            "batch_id": str(batch_id), "export_date": batch.export_date.isoformat(),
            "content_hash": batch.content_hash,
            "visits": [r.payload for r in rows if r.kind == "visit"],
            "claims": [r.payload for r in rows if r.kind == "claim"],
        }
        data = json.dumps(doc, sort_keys=True, separators=(",", ":"), default=str).encode()
        key = ClinicObjects(store, clinic_id).put(SOURCE, PURPOSE, batch_id, data)
        batch.payload_object_key = key
        write_audit(s, "import_payload_stored", "ok", clinic_id, None, "import_batch", batch_id,
                    {"rows": len(rows), "bytes": len(data)})
        return key


def read_payload(store: BlobStore, clinic_id: uuid.UUID, key: str) -> bytes:
    return ClinicObjects(store, clinic_id).get(key)


def purge_payloads(engine: Engine, store: BlobStore, clinic_id: uuid.UUID, now: datetime) -> int:
    """`retention_purge` for one clinic. Returns the number of objects removed."""
    removed = 0
    objects = ClinicObjects(store, clinic_id)
    with tenant_session(engine, clinic_id) as s:
        live = {b.payload_object_key: b for b in s.scalars(select(ImportBatch).where(
            ImportBatch.payload_object_key.isnot(None), ImportBatch.payload_deleted_at.is_(None)))}
        # (a) by the database: completed more than 24 hours ago, whatever the batch status
        for key, b in list(live.items()):
            if key and b.completed_at is not None and b.completed_at < now - RETENTION:
                objects.delete(key)
                b.payload_deleted_at = now
                live.pop(key)
                removed += 1
        # (b) by the store: too old by its own timestamp, or not recorded in the database at all
        for obj in objects.list_objects(SOURCE, PURPOSE):
            age = now - obj.last_modified
            orphan = obj.key not in live
            if age > RETENTION or (orphan and age > ORPHAN_GRACE):
                objects.delete(obj.key)
                held = live.get(obj.key)
                if held is not None:
                    held.payload_deleted_at = now
                removed += 1
        if removed:
            write_audit(s, "import_payload_purged", "ok", clinic_id, None, None, None, {"objects": removed})
    return removed


def sweep_expired_objects(store: BlobStore, now: datetime) -> int:
    """Bucket-wide backstop, hourly from the worker: every payload object older than 24 hours, for any
    clinic, including clinics whose rows are already gone."""
    removed = 0
    for obj in store.list_objects("clinic/"):
        parts = obj.key.split("/")
        if len(parts) == 5 and parts[2] == SOURCE and parts[3] == PURPOSE and now - obj.last_modified > RETENTION:
            store.delete(obj.key)
            removed += 1
    return removed


def delete_clinic_objects(store: BlobStore, clinic_id: uuid.UUID) -> int:
    """For `deletion_execute` (MH-11 b, not built in B2): removes every object of the clinic."""
    return ClinicObjects(store, clinic_id).delete_all()
