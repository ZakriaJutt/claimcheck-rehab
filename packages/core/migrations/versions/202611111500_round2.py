"""Fix round 2 (B1-010, B1-008 open part).

- `finding.latest_limit_date`: the latest possible limit when the true limit is uncertain (WSBC-02).
- The cross-clinic queue functions get a dedicated owner role `claimcheck_queue_owner` (NOLOGIN,
  NOSUPERUSER, NOBYPASSRLS), the same locally and in production. It reaches `job` and `clinic` through
  row-level-security policies granted to that role only, and holds no other privilege. search_path is
  pinned with pg_temp last.

Revision ID: 202611111500
Revises: 202611111200
"""

from alembic import op

revision = "202611111500"
down_revision = "202611111200"
branch_labels = None
depends_on = None

OWNER = "claimcheck_queue_owner"
QUEUE_FUNCTIONS = (
    "cc_job_claim(uuid, integer, text[])",
    "cc_job_complete(uuid, uuid, boolean, text, boolean)",
    "cc_job_expire_leases()",
    "cc_enqueue_per_clinic(text, text, jsonb, uuid)",
)


def upgrade() -> None:
    op.execute("ALTER TABLE finding ADD COLUMN latest_limit_date date")
    op.execute(f"""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{OWNER}') THEN
            CREATE ROLE {OWNER} NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
          END IF;
        END $$""")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {OWNER}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON job TO {OWNER}")
    op.execute(f"GRANT SELECT ON clinic TO {OWNER}")
    op.execute(f"CREATE POLICY job_queue_owner ON job TO {OWNER} USING (true) WITH CHECK (true)")
    op.execute(f"CREATE POLICY clinic_queue_owner ON clinic FOR SELECT TO {OWNER} USING (true)")
    for fn in QUEUE_FUNCTIONS:
        op.execute(f"ALTER FUNCTION {fn} OWNER TO {OWNER}")
        op.execute(f"ALTER FUNCTION {fn} SET search_path = pg_catalog, public, pg_temp")
        op.execute(f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC")
    # Ownership change keeps EXECUTE for claimcheck_worker (granted in 202611111200).


def downgrade() -> None:
    for fn in QUEUE_FUNCTIONS:
        op.execute(f"ALTER FUNCTION {fn} OWNER TO CURRENT_USER")
        op.execute(f"ALTER FUNCTION {fn} SET search_path = public, pg_temp")
    op.execute("DROP POLICY IF EXISTS clinic_queue_owner ON clinic")
    op.execute("DROP POLICY IF EXISTS job_queue_owner ON job")
    op.execute(f"REVOKE ALL ON job, clinic FROM {OWNER}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {OWNER}")
    op.execute("ALTER TABLE finding DROP COLUMN latest_limit_date")
