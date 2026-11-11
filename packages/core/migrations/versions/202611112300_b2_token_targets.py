"""B2 review observation: refuse a password equal to the account's email at invitation acceptance and at
reset. The API needs the address a live link belongs to before it hashes the new password, so two
read-only lookups by token hash are added (owned by `claimcheck_auth_owner`, EXECUTE for the app only).
They answer only for a link that is unused and unexpired, and return the address the link was sent to.

Revision ID: 202611112300
Revises: 202611112200
"""

from alembic import op

revision = "202611112300"
down_revision = "202611112200"
branch_labels = None
depends_on = None

OWNER = "claimcheck_auth_owner"
APP = "claimcheck_app"
NEW = ("cc_auth_invite_target(text)", "cc_auth_reset_target(text)")

SQL = r"""
CREATE FUNCTION cc_auth_invite_target(p_token_hash text)
RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT i.email::text FROM invite i
  WHERE i.token_hash = p_token_hash AND i.accepted_at IS NULL AND i.expires_at > now();
$$;

CREATE FUNCTION cc_auth_reset_target(p_token_hash text)
RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT u.email::text FROM password_reset r JOIN app_user u ON u.id = r.user_id
  WHERE r.token_hash = p_token_hash AND r.used_at IS NULL AND r.expires_at > now();
$$;
"""


def upgrade() -> None:
    op.execute(SQL)
    for fn in NEW:
        op.execute(f"ALTER FUNCTION {fn} OWNER TO {OWNER}")
        op.execute(f"ALTER FUNCTION {fn} SET search_path = pg_catalog, public, pg_temp")
        op.execute(f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO {APP}")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS " + ", ".join(NEW))
