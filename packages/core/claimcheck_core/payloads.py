"""The minimised import payload in the object store (B2, AD-11).

After a batch completes, the worker writes the rows exactly as the browser sent them (the 16 fields and
two ordinals; nothing else ever reaches the server) as one JSON object under the clinic's prefix.
Guard-rejected and failed batches store nothing. Retention follows `import_row` (schema.md section 9):
24 hours after completion, except that the latest completed batch with refused rows is kept until a later
batch for the clinic completes. Clinic deletion removes every object under the clinic's prefix.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import Engine, select

from claimcheck_core.audit import write_audit
from claimcheck_core.models import ImportBatch, ImportRow
from claimcheck_core.storage import BlobStore, ClinicObjects
from claimcheck_core.tenancy import tenant_session

SOURCE = "jane_export"
PURPOSE = "import_payload"
RETENTION = timedelta(hours=24)
DONE = ("completed", "completed_with_rejects")


def archive_payload(engine: Engine, store: BlobStore, clinic_id: uuid.UUID, batch_id: uuid.UUID) -> str | None:
    """Idempotent: a batch already archived (or not completed) is left alone. Returns the key written."""
    with tenant_session(engine, clinic_id) as s:
        batch = s.get(ImportBatch, batch_id, with_for_update=True)
        if batch is None or batch.status not in DONE or batch.payload_object_key or batch.payload_deleted_at:
            return None
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
    """The object part of `retention_purge` for one clinic. Returns the number of objects removed."""
    removed = 0
    with tenant_session(engine, clinic_id) as s:
        latest = s.scalars(select(ImportBatch).where(ImportBatch.status.in_(DONE))
                           .order_by(ImportBatch.completed_at.desc()).limit(1)).first()
        keep = latest.id if latest is not None and latest.status == "completed_with_rejects" else None
        due = list(s.scalars(select(ImportBatch).where(
            ImportBatch.payload_object_key.isnot(None), ImportBatch.payload_deleted_at.is_(None),
            ImportBatch.status.in_(DONE), ImportBatch.completed_at < now - RETENTION)))
        objects = ClinicObjects(store, clinic_id)
        for b in due:
            if b.id == keep or b.payload_object_key is None:
                continue
            objects.delete(b.payload_object_key)
            b.payload_deleted_at = now
            removed += 1
        if removed:
            write_audit(s, "import_payload_purged", "ok", clinic_id, None, None, None, {"objects": removed})
    return removed


def delete_clinic_objects(store: BlobStore, clinic_id: uuid.UUID) -> int:
    """For `deletion_execute` (MH-11 b, not built in B2): removes every object of the clinic."""
    return ClinicObjects(store, clinic_id).delete_all()
