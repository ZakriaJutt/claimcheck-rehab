"""Fix round 1 (B1-002, B1-007, B1-008): visit status `rules_not_evaluated`, payer `UNKNOWN`, and a
separate worker role for the cross-clinic job-queue functions.

The role `claimcheck_worker` (NOSUPERUSER, NOBYPASSRLS) is created outside migrations, like
`claimcheck_app`. Expand only: no column is dropped.

Revision ID: 202611111200
Revises: 202611110900
"""

from alembic import op

revision = "202611111200"
down_revision = "202611110900"
branch_labels = None
depends_on = None

APP = "claimcheck_app"
WORKER = "claimcheck_worker"
QUEUE_FUNCTIONS = (
    "cc_job_claim(uuid, integer, text[])",
    "cc_job_complete(uuid, uuid, boolean, text, boolean)",
    "cc_job_expire_leases()",
    "cc_enqueue_per_clinic(text, text, jsonb, uuid)",
)


def upgrade() -> None:
    op.execute("ALTER TABLE visit DROP CONSTRAINT visit_check_status_check")
    op.execute("ALTER TABLE visit ADD CONSTRAINT visit_check_status_check CHECK (check_status IS NULL OR "
               "check_status IN ('in_scope','rules_not_evaluated','could_not_check','no_rules_applied'))")
    for table in ("visit", "claim"):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_payer_check")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {table}_payer_check "
                   "CHECK (payer IN ('ICBC','WSBC','OTHER','UNKNOWN'))")
    op.execute("COMMENT ON COLUMN visit.first_rejected_on IS "
               "'Deprecated in fix round 1 (B1-003): not written or read; WSBC-02 derives an earliest-possible "
               "bound from visit_snapshot. Removed by a later contract migration.'")
    # The API role may no longer touch the job queue across clinics (B1-008).
    for fn in QUEUE_FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {fn} FROM {APP}")
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO {WORKER}")
    op.execute(f"GRANT EXECUTE ON FUNCTION cc_current_clinic() TO {WORKER}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {WORKER}")
    op.execute(f"GRANT SELECT, UPDATE ON clinic TO {WORKER}")
    op.execute(f"GRANT SELECT ON app_user, export_profile, rule_version, alembic_version TO {WORKER}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON import_batch, claim, visit, evaluation_run, finding, item TO {WORKER}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON import_row TO {WORKER}")
    op.execute(f"GRANT SELECT, INSERT ON visit_snapshot, item_event, audit_event, job TO {WORKER}")


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {WORKER}")
    for fn in QUEUE_FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {fn} FROM {WORKER}")
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO {APP}")
    op.execute(f"REVOKE ALL ON FUNCTION cc_current_clinic() FROM {WORKER}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {WORKER}")
    op.execute("COMMENT ON COLUMN visit.first_rejected_on IS NULL")
    for table in ("visit", "claim"):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_payer_check")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {table}_payer_check CHECK (payer IN ('ICBC','WSBC','OTHER'))")
    op.execute("ALTER TABLE visit DROP CONSTRAINT visit_check_status_check")
    op.execute("ALTER TABLE visit ADD CONSTRAINT visit_check_status_check CHECK (check_status IS NULL OR "
               "check_status IN ('in_scope','could_not_check','no_rules_applied'))")
