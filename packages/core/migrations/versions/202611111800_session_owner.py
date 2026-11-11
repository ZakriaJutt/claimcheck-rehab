"""Round-3 hardening (B1-008 residual): the session lookup gets a dedicated non-superuser owner.

`cc_session_principal` was owned by the migration user (a superuser locally). It is now owned by
`claimcheck_session_owner` (NOLOGIN, NOSUPERUSER, NOBYPASSRLS, NOINHERIT), which holds only what the
function needs: SELECT, UPDATE on `session` and SELECT on `app_user`, reached through a policy on
`app_user` granted to that role alone (`app_user` has FORCE ROW LEVEL SECURITY). search_path is pinned
to `pg_catalog, public, pg_temp`. EXECUTE is held by the owner and `claimcheck_app` only.

Revision ID: 202611111800
Revises: 202611111500
"""

from alembic import op

revision = "202611111800"
down_revision = "202611111500"
branch_labels = None
depends_on = None

OWNER = "claimcheck_session_owner"
APP = "claimcheck_app"
WORKER = "claimcheck_worker"
FN = "cc_session_principal(text, integer)"


def upgrade() -> None:
    op.execute(f"""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{OWNER}') THEN
            CREATE ROLE {OWNER} NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
          END IF;
        END $$""")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {OWNER}")
    op.execute(f"GRANT SELECT, UPDATE ON session TO {OWNER}")
    op.execute(f"GRANT SELECT ON app_user TO {OWNER}")
    op.execute(f"CREATE POLICY app_user_session_owner ON app_user FOR SELECT TO {OWNER} USING (true)")
    op.execute(f"ALTER FUNCTION {FN} OWNER TO {OWNER}")
    op.execute(f"ALTER FUNCTION {FN} SET search_path = pg_catalog, public, pg_temp")
    op.execute(f"REVOKE ALL ON FUNCTION {FN} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {FN} FROM {WORKER}")
    op.execute(f"GRANT EXECUTE ON FUNCTION {FN} TO {APP}")


def downgrade() -> None:
    op.execute(f"ALTER FUNCTION {FN} OWNER TO CURRENT_USER")
    op.execute(f"ALTER FUNCTION {FN} SET search_path = public, pg_temp")
    op.execute("DROP POLICY IF EXISTS app_user_session_owner ON app_user")
    op.execute(f"REVOKE ALL ON session, app_user FROM {OWNER}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {OWNER}")
