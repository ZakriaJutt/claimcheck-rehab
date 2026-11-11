"""B2 security fixes, round 1 (B2-S01): failure limits are checked and reserved in one statement.

`cc_auth_rate_reserve` locks the bucket, drops attempts outside the window, counts the rest and, only when
the count is under the limit, inserts one attempt and returns its id, all in one call made *before* the
password or code is verified. Parallel requests therefore cannot all pass a separate look-then-record
check: at most `p_max` are ever evaluated per window. A successful verification gives its slot back with
`cc_auth_rate_release`, so the limits count failures only. `cc_auth_rate_peek` (look without recording)
is dropped.

Revision ID: 202611112200
Revises: 202611112000
"""

from alembic import op

revision = "202611112200"
down_revision = "202611112000"
branch_labels = None
depends_on = None

OWNER = "claimcheck_auth_owner"
APP = "claimcheck_app"
NEW = ("cc_auth_rate_reserve(text, integer, integer)", "cc_auth_rate_release(uuid)")

SQL = r"""
CREATE FUNCTION cc_auth_rate_reserve(p_bucket text, p_window_seconds integer, p_max integer)
RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE n integer; v_id uuid;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(p_bucket, 0));
  DELETE FROM auth_attempt WHERE bucket = p_bucket AND created_at < now() - make_interval(secs => p_window_seconds);
  SELECT count(*) INTO n FROM auth_attempt WHERE bucket = p_bucket;
  IF n >= p_max THEN RETURN NULL; END IF;
  INSERT INTO auth_attempt (bucket) VALUES (p_bucket) RETURNING id INTO v_id;
  RETURN v_id;
END $$;

CREATE FUNCTION cc_auth_rate_release(p_id uuid)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE n integer;
BEGIN
  DELETE FROM auth_attempt WHERE id = p_id;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END $$;
"""


def upgrade() -> None:
    op.execute("DROP FUNCTION cc_auth_rate_peek(text, integer, integer)")
    op.execute(SQL)
    for fn in NEW:
        op.execute(f"ALTER FUNCTION {fn} OWNER TO {OWNER}")
        op.execute(f"ALTER FUNCTION {fn} SET search_path = pg_catalog, public, pg_temp")
        op.execute(f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO {APP}")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS " + ", ".join(NEW))
    op.execute(r"""
CREATE FUNCTION cc_auth_rate_peek(p_bucket text, p_window_seconds integer, p_max integer)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT count(*) < p_max FROM auth_attempt
  WHERE bucket = p_bucket AND created_at >= now() - make_interval(secs => p_window_seconds);
$$""")
    fn = "cc_auth_rate_peek(text, integer, integer)"
    op.execute(f"ALTER FUNCTION {fn} OWNER TO {OWNER}")
    op.execute(f"ALTER FUNCTION {fn} SET search_path = pg_catalog, public, pg_temp")
    op.execute(f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO {APP}")
