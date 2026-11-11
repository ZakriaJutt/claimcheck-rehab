"""Worker entry point: lease-expiry sweep, scheduler tick, claim one job at a time, heartbeat.

python -m claimcheck_worker.main [--once]
"""

from __future__ import annotations

import argparse
import signal
import time
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from claimcheck_core import logging as cclog
from claimcheck_core.dates import CLINIC_TZ, local_today
from claimcheck_core.db import get_engine
from claimcheck_core.evaluation import evaluate_clinic, load_published_versions, staleness_check
from claimcheck_core.identifier_scan import identifier_scan
from claimcheck_core.imports import finalize
from claimcheck_core.jobs import ClaimedJob, claim_next, complete, enqueue_per_clinic, expire_leases
from claimcheck_core.payloads import archive_payload, purge_payloads, sweep_expired_objects
from claimcheck_core.rules.catalogue import rule_set_hash
from claimcheck_core.settings import get_settings
from claimcheck_core.storage import get_store
from claimcheck_core.tenancy import system_session

_log = cclog.get_logger("worker")
HEARTBEAT = Path(__file__).resolve().parents[3] / ".run" / "worker-heartbeat"
DAILY_HOUR = 5  # 05:00 Pacific (TRD jobs table)
_stop = False


class PermanentJobError(Exception):
    """Not worth retrying (e.g. a missing batch)."""


def _on_date(job: ClaimedJob) -> date:
    raw = job.payload.get("on_date")
    return date.fromisoformat(raw) if raw else local_today()


def run_job(job: ClaimedJob) -> None:
    engine = get_engine()
    if job.clinic_id is None:
        raise PermanentJobError("job without clinic")
    if job.kind == "import_finalize":
        batch_id = uuid.UUID(job.payload["batch_id"])
        finalize(engine, job.clinic_id, batch_id, _on_date(job))
        # B2 (AD-11): keep the minimised payload in the object store; a storage failure retries the job,
        # and the repeated finalize is a no-op.
        archive_payload(engine, get_store(), job.clinic_id, batch_id)
    elif job.kind == "evaluate_clinic":
        evaluate_clinic(engine, job.clinic_id, _on_date(job), job.payload.get("trigger", "daily"))
    elif job.kind == "identifier_scan":
        identifier_scan(engine, job.clinic_id, _on_date(job))
    elif job.kind == "retention_purge":
        purge_payloads(engine, get_store(), job.clinic_id, datetime.now(tz=UTC))
    elif job.kind == "staleness_check":
        staleness_check(engine, job.clinic_id, datetime.now(tz=UTC))
    else:
        raise PermanentJobError("unknown job kind")


def process_one() -> bool:
    engine = get_engine()
    settings = get_settings()
    job = claim_next(engine, settings.job_lease_seconds)
    if job is None:
        return False
    token = cclog.set_correlation_id(str(job.correlation_id))
    try:
        cclog.log_event(_log, "job_started", job_id=str(job.id), kind=job.kind, attempt=job.attempt)
        try:
            run_job(job)
        except PermanentJobError as exc:
            complete(engine, job.id, job.lease_token, ok=False, error_code=type(exc).__name__, retryable=False)
            return True
        except Exception as exc:  # noqa: BLE001 - recorded as a code, retried with backoff
            cclog.log_event(_log, "job_error", 40, job_id=str(job.id), error_type=type(exc).__name__)
            complete(engine, job.id, job.lease_token, ok=False, error_code=type(exc).__name__, retryable=True)
            return True
        complete(engine, job.id, job.lease_token, ok=True)
        cclog.log_event(_log, "job_succeeded", job_id=str(job.id), kind=job.kind)
        return True
    finally:
        cclog.reset_correlation_id(token)


def schedule_daily(now: datetime) -> int:
    """Enqueue the day's per-clinic jobs once local time passes 05:00; idempotent on the key."""
    local = now.astimezone(CLINIC_TZ)
    if local.hour < DAILY_HOUR:
        return 0
    engine = get_engine()
    with system_session(engine) as s:
        rhash = rule_set_hash(load_published_versions(s))
    d = local.date().isoformat()
    n = enqueue_per_clinic(engine, "evaluate_clinic", f"daily:{d}:{rhash}", {"trigger": "daily", "on_date": d})
    n += enqueue_per_clinic(engine, "identifier_scan", f"daily:{d}", {"on_date": d})
    n += enqueue_per_clinic(engine, "staleness_check", f"daily:{d}", {})
    return n


_last_sweep_hour: str | None = None


def schedule_hourly(now: datetime) -> int:
    """B2-S02: the payload purge runs at least hourly (per clinic, as a job) and the bucket-wide sweep of
    expired objects runs once an hour in this process. Idempotent per hour."""
    global _last_sweep_hour
    hour = now.astimezone(UTC).strftime("%Y-%m-%dT%H")
    n = enqueue_per_clinic(get_engine(), "retention_purge", f"hourly:{hour}", {})
    if _last_sweep_hour != hour:
        try:
            sweep_expired_objects(get_store(), now)
            _last_sweep_hour = hour
        except Exception as exc:  # noqa: BLE001 - retried next loop; the lifecycle rule is the backstop
            cclog.log_event(_log, "sweep_failed", 40, error_type=type(exc).__name__)
    return n


def heartbeat() -> None:
    HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT.write_text(datetime.now(tz=UTC).isoformat())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claimcheck-worker")
    parser.add_argument("--once", action="store_true", help="drain due jobs, then exit")
    parser.add_argument("--no-schedule", action="store_true", help="do not enqueue daily jobs")
    args = parser.parse_args(argv)
    settings = get_settings()
    cclog.configure(settings.log_level)

    def _sig(*_: object) -> None:
        global _stop
        _stop = True

    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)
    cclog.log_event(_log, "worker_started", env=settings.app_env)
    while not _stop:
        heartbeat()
        expire_leases(get_engine())
        if not args.no_schedule:
            schedule_daily(datetime.now(tz=UTC))
            schedule_hourly(datetime.now(tz=UTC))
        worked = process_one()
        if args.once and not worked:
            break
        if not worked:
            time.sleep(1.0)
    cclog.log_event(_log, "worker_stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
