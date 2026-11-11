"""B2: sign-in (password, TOTP, recovery codes, invitations, password reset, rate limits) and the
object-store record of the minimised import payload (AD-11).

Tables: `totp_credential`, `recovery_code`, `invite` (clinic-owned, RLS), `password_reset`,
`auth_attempt`; columns `import_batch.payload_object_key`, `import_batch.payload_deleted_at`.

Every pre-authentication read or write goes through `SECURITY DEFINER` functions owned by the dedicated
role `claimcheck_auth_owner` (NOLOGIN, NOSUPERUSER, NOBYPASSRLS, NOINHERIT); search_path is pinned with
pg_temp last; EXECUTE is granted to `claimcheck_app` only. The application role has no grant on the
credential tables at all.

Revision ID: 202611112000
Revises: 202611111800
"""

from alembic import op

revision = "202611112000"
down_revision = "202611111800"
branch_labels = None
depends_on = None

OWNER = "claimcheck_auth_owner"
APP = "claimcheck_app"

TABLES_SQL = """
CREATE TABLE totp_credential (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  user_id uuid NOT NULL UNIQUE REFERENCES app_user(id),
  secret_enc bytea NOT NULL,
  confirmed_at timestamptz,
  last_used_step bigint
);

CREATE TABLE recovery_code (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  user_id uuid NOT NULL REFERENCES app_user(id),
  code_hash text NOT NULL,
  used_at timestamptz,
  CONSTRAINT recovery_code_user_id_code_hash_key UNIQUE (user_id, code_hash)
);

CREATE TABLE invite (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  clinic_id uuid NOT NULL REFERENCES clinic(id),
  email citext NOT NULL,
  role text NOT NULL,
  token_hash text NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  accepted_at timestamptz,
  invited_by uuid REFERENCES app_user(id),
  CONSTRAINT invite_role_check CHECK (role IN ('owner','staff'))
);
CREATE UNIQUE INDEX ux_invite_pending ON invite (clinic_id, email) WHERE accepted_at IS NULL;

CREATE TABLE password_reset (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  user_id uuid NOT NULL REFERENCES app_user(id),
  token_hash text NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  used_at timestamptz
);

CREATE TABLE auth_attempt (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  bucket text NOT NULL
);
CREATE INDEX ix_auth_attempt_bucket_created ON auth_attempt (bucket, created_at);

ALTER TABLE import_batch ADD COLUMN payload_object_key text;
ALTER TABLE import_batch ADD COLUMN payload_deleted_at timestamptz;
"""

FUNCTIONS_SQL = r"""
-- Pre-authentication lookup by email. Returns the hash so the API can verify it (argon2id).
CREATE FUNCTION cc_auth_lookup(p_email text)
RETURNS TABLE(user_id uuid, clinic_id uuid, role text, password_hash text, disabled boolean,
              totp_confirmed boolean)
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT u.id, u.clinic_id, u.role, u.password_hash, u.disabled_at IS NOT NULL,
         EXISTS (SELECT 1 FROM totp_credential t WHERE t.user_id = u.id AND t.confirmed_at IS NOT NULL)
  FROM app_user u WHERE u.email = p_email::citext;
$$;

-- Open a session. A session with mfa_passed = false is a pending sign-in: cc_session_principal never
-- accepts it, so it reaches only the second-factor endpoints.
CREATE FUNCTION cc_auth_session_open(p_user uuid, p_token_hash text, p_mfa boolean, p_minutes integer)
RETURNS uuid
LANGUAGE sql SECURITY DEFINER AS $$
  INSERT INTO session (user_id, token_hash, mfa_passed, last_seen_at, expires_at)
  SELECT u.id, p_token_hash, p_mfa, now(), now() + make_interval(mins => p_minutes)
  FROM app_user u WHERE u.id = p_user AND u.disabled_at IS NULL
  RETURNING id;
$$;

-- A live pending sign-in and the user's second-factor state.
CREATE FUNCTION cc_auth_pending(p_token_hash text)
RETURNS TABLE(user_id uuid, clinic_id uuid, role text, secret_enc bytea, totp_confirmed boolean,
              last_used_step bigint)
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT u.id, u.clinic_id, u.role, t.secret_enc, t.confirmed_at IS NOT NULL, t.last_used_step
  FROM session s JOIN app_user u ON u.id = s.user_id
  LEFT JOIN totp_credential t ON t.user_id = u.id
  WHERE s.token_hash = p_token_hash AND NOT s.mfa_passed AND s.revoked_at IS NULL
    AND s.expires_at > now() AND u.disabled_at IS NULL;
$$;

-- Store a new (unconfirmed) TOTP secret for the user of a pending sign-in. A confirmed factor is never
-- replaced this way.
CREATE FUNCTION cc_auth_totp_enrol(p_pending_hash text, p_secret_enc bytea)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE v_user uuid; n integer;
BEGIN
  SELECT s.user_id INTO v_user FROM session s JOIN app_user u ON u.id = s.user_id
  WHERE s.token_hash = p_pending_hash AND NOT s.mfa_passed AND s.revoked_at IS NULL AND s.expires_at > now()
    AND u.disabled_at IS NULL;
  IF v_user IS NULL THEN RETURN false; END IF;
  INSERT INTO totp_credential (user_id, secret_enc) VALUES (v_user, p_secret_enc)
  ON CONFLICT (user_id) DO UPDATE SET secret_enc = EXCLUDED.secret_enc, last_used_step = NULL
  WHERE totp_credential.confirmed_at IS NULL;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n = 1;
END $$;

-- Complete the second factor: exactly one of a TOTP time step (already verified by the API against the
-- decrypted secret; refused here if not later than the last step used) or a recovery-code hash (used
-- once). The pending session is revoked and a new full session is opened under a new token (rotation).
CREATE FUNCTION cc_auth_mfa_complete(p_pending_hash text, p_new_hash text, p_step bigint, p_recovery_hash text,
                                     p_minutes integer)
RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE v_user uuid; v_sess uuid; n integer; v_new uuid;
BEGIN
  IF (p_step IS NULL) = (p_recovery_hash IS NULL) THEN RETURN NULL; END IF;
  SELECT s.id, s.user_id INTO v_sess, v_user FROM session s JOIN app_user u ON u.id = s.user_id
  WHERE s.token_hash = p_pending_hash AND NOT s.mfa_passed AND s.revoked_at IS NULL AND s.expires_at > now()
    AND u.disabled_at IS NULL
  FOR UPDATE OF s;
  IF v_user IS NULL THEN RETURN NULL; END IF;
  IF p_step IS NOT NULL THEN
    UPDATE totp_credential SET last_used_step = p_step, confirmed_at = coalesce(confirmed_at, now())
    WHERE user_id = v_user AND (last_used_step IS NULL OR last_used_step < p_step);
  ELSE
    UPDATE recovery_code SET used_at = now()
    WHERE user_id = v_user AND code_hash = p_recovery_hash AND used_at IS NULL
      AND EXISTS (SELECT 1 FROM totp_credential t WHERE t.user_id = v_user AND t.confirmed_at IS NOT NULL);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  IF n <> 1 THEN RETURN NULL; END IF;
  UPDATE session SET revoked_at = now() WHERE id = v_sess;
  INSERT INTO session (user_id, token_hash, mfa_passed, last_seen_at, expires_at)
  VALUES (v_user, p_new_hash, true, now(), now() + make_interval(mins => p_minutes)) RETURNING id INTO v_new;
  RETURN v_user;
END $$;

-- Replace the recovery codes of the user of a live full session.
CREATE FUNCTION cc_auth_recovery_set(p_session_hash text, p_hashes text[])
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE v_user uuid; n integer;
BEGIN
  SELECT s.user_id INTO v_user FROM session s
  WHERE s.token_hash = p_session_hash AND s.mfa_passed AND s.revoked_at IS NULL AND s.expires_at > now();
  IF v_user IS NULL THEN RETURN 0; END IF;
  DELETE FROM recovery_code WHERE user_id = v_user;
  INSERT INTO recovery_code (user_id, code_hash) SELECT v_user, unnest(p_hashes);
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END $$;

CREATE FUNCTION cc_auth_session_revoke(p_token_hash text)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE n integer;
BEGIN
  UPDATE session SET revoked_at = now() WHERE token_hash = p_token_hash AND revoked_at IS NULL;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END $$;

-- Fixed-window rate limit: records one attempt in the bucket and says whether it is within p_max.
CREATE FUNCTION cc_auth_rate_hit(p_bucket text, p_window_seconds integer, p_max integer)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE n integer;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(p_bucket, 0));
  DELETE FROM auth_attempt WHERE bucket = p_bucket AND created_at < now() - make_interval(secs => p_window_seconds);
  SELECT count(*) INTO n FROM auth_attempt WHERE bucket = p_bucket;
  INSERT INTO auth_attempt (bucket) VALUES (p_bucket);
  RETURN n < p_max;
END $$;

-- Whether the bucket is still under p_max, without recording an attempt (failures-only limits).
CREATE FUNCTION cc_auth_rate_peek(p_bucket text, p_window_seconds integer, p_max integer)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT count(*) < p_max FROM auth_attempt
  WHERE bucket = p_bucket AND created_at >= now() - make_interval(secs => p_window_seconds);
$$;

-- Accept an invitation: single use, before expiry; creates the user in the invitation's clinic.
CREATE FUNCTION cc_auth_invite_accept(p_token_hash text, p_password_hash text)
RETURNS TABLE(user_id uuid, clinic_id uuid, outcome text)
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE v invite%ROWTYPE; v_user uuid;
BEGIN
  SELECT * INTO v FROM invite i WHERE i.token_hash = p_token_hash FOR UPDATE;
  IF NOT FOUND THEN RETURN QUERY SELECT NULL::uuid, NULL::uuid, 'invalid'; RETURN; END IF;
  IF v.accepted_at IS NOT NULL THEN RETURN QUERY SELECT NULL::uuid, v.clinic_id, 'used'; RETURN; END IF;
  IF v.expires_at <= now() THEN RETURN QUERY SELECT NULL::uuid, v.clinic_id, 'expired'; RETURN; END IF;
  IF EXISTS (SELECT 1 FROM app_user u WHERE u.email = v.email) THEN
    RETURN QUERY SELECT NULL::uuid, v.clinic_id, 'email_taken'; RETURN;
  END IF;
  INSERT INTO app_user (clinic_id, email, password_hash, role)
  VALUES (v.clinic_id, v.email, p_password_hash, v.role) RETURNING id INTO v_user;
  UPDATE invite SET accepted_at = now() WHERE id = v.id;
  RETURN QUERY SELECT v_user, v.clinic_id, 'accepted';
END $$;

-- Password reset: a new link supersedes older unused ones.
CREATE FUNCTION cc_auth_reset_create(p_user uuid, p_token_hash text, p_minutes integer)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM app_user WHERE id = p_user AND disabled_at IS NULL) THEN RETURN false; END IF;
  UPDATE password_reset SET used_at = now() WHERE user_id = p_user AND used_at IS NULL;
  INSERT INTO password_reset (user_id, token_hash, expires_at)
  VALUES (p_user, p_token_hash, now() + make_interval(mins => p_minutes));
  RETURN true;
END $$;

-- Complete a reset: single use, before expiry; sets the new hash and ends every session of the user.
-- It does not sign the user in, so the second factor is still required (ASVS 6.4.3).
CREATE FUNCTION cc_auth_reset_complete(p_token_hash text, p_password_hash text)
RETURNS TABLE(user_id uuid, clinic_id uuid, outcome text)
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE v password_reset%ROWTYPE; v_clinic uuid;
BEGIN
  SELECT * INTO v FROM password_reset r WHERE r.token_hash = p_token_hash FOR UPDATE;
  IF NOT FOUND THEN RETURN QUERY SELECT NULL::uuid, NULL::uuid, 'invalid'; RETURN; END IF;
  SELECT u.clinic_id INTO v_clinic FROM app_user u WHERE u.id = v.user_id;
  IF v.used_at IS NOT NULL THEN RETURN QUERY SELECT NULL::uuid, v_clinic, 'used'; RETURN; END IF;
  IF v.expires_at <= now() THEN RETURN QUERY SELECT NULL::uuid, v_clinic, 'expired'; RETURN; END IF;
  UPDATE password_reset SET used_at = now() WHERE id = v.id;
  UPDATE app_user SET password_hash = p_password_hash WHERE id = v.user_id AND disabled_at IS NULL;
  UPDATE session SET revoked_at = now() WHERE session.user_id = v.user_id AND revoked_at IS NULL;
  RETURN QUERY SELECT v.user_id, v_clinic, 'reset';
END $$;

-- Remove a user: only a live owner session of the same clinic may do it, never on itself. Every
-- session of the removed user ends at once (ASVS 7.4.2).
CREATE FUNCTION cc_auth_user_disable(p_actor_hash text, p_target uuid, p_idle_minutes integer)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE v_actor uuid; v_clinic uuid; n integer;
BEGIN
  SELECT u.id, u.clinic_id INTO v_actor, v_clinic FROM session s JOIN app_user u ON u.id = s.user_id
  WHERE s.token_hash = p_actor_hash AND s.mfa_passed AND s.revoked_at IS NULL AND s.expires_at > now()
    AND s.last_seen_at > now() - make_interval(mins => p_idle_minutes)
    AND u.disabled_at IS NULL AND u.role = 'owner';
  IF v_actor IS NULL OR v_actor = p_target THEN RETURN 0; END IF;
  UPDATE app_user SET disabled_at = now() WHERE id = p_target AND app_user.clinic_id = v_clinic
    AND disabled_at IS NULL;
  GET DIAGNOSTICS n = ROW_COUNT;
  IF n = 1 THEN
    UPDATE session SET revoked_at = now() WHERE user_id = p_target AND revoked_at IS NULL;
  END IF;
  RETURN n;
END $$;
"""

FUNCTIONS = (
    "cc_auth_lookup(text)",
    "cc_auth_session_open(uuid, text, boolean, integer)",
    "cc_auth_pending(text)",
    "cc_auth_totp_enrol(text, bytea)",
    "cc_auth_mfa_complete(text, text, bigint, text, integer)",
    "cc_auth_recovery_set(text, text[])",
    "cc_auth_session_revoke(text)",
    "cc_auth_rate_hit(text, integer, integer)",
    "cc_auth_rate_peek(text, integer, integer)",
    "cc_auth_invite_accept(text, text)",
    "cc_auth_reset_create(uuid, text, integer)",
    "cc_auth_reset_complete(text, text)",
    "cc_auth_user_disable(text, uuid, integer)",
)


def upgrade() -> None:
    op.execute(TABLES_SQL)
    op.execute("ALTER TABLE invite ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invite FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY invite_tenant ON invite USING (clinic_id = cc_current_clinic()) "
               "WITH CHECK (clinic_id = cc_current_clinic())")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON invite TO {APP}")

    op.execute(f"""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{OWNER}') THEN
            CREATE ROLE {OWNER} NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
          END IF;
        END $$""")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {OWNER}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON session, app_user TO {OWNER}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON totp_credential, password_reset TO {OWNER}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON recovery_code TO {OWNER}")
    op.execute(f"GRANT SELECT, UPDATE ON invite TO {OWNER}")
    op.execute(f"GRANT SELECT, INSERT, DELETE ON auth_attempt TO {OWNER}")
    op.execute(f"CREATE POLICY app_user_auth_owner ON app_user TO {OWNER} USING (true) WITH CHECK (true)")
    op.execute(f"CREATE POLICY invite_auth_owner ON invite TO {OWNER} USING (true) WITH CHECK (true)")

    op.execute(FUNCTIONS_SQL)
    for fn in FUNCTIONS:
        op.execute(f"ALTER FUNCTION {fn} OWNER TO {OWNER}")
        op.execute(f"ALTER FUNCTION {fn} SET search_path = pg_catalog, public, pg_temp")
        op.execute(f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO {APP}")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS " + ", ".join(FUNCTIONS))
    op.execute("DROP POLICY IF EXISTS app_user_auth_owner ON app_user")
    op.execute(f"REVOKE ALL ON session, app_user FROM {OWNER}")
    op.execute("ALTER TABLE import_batch DROP COLUMN payload_deleted_at")
    op.execute("ALTER TABLE import_batch DROP COLUMN payload_object_key")
    for t in ("auth_attempt", "password_reset", "invite", "recovery_code", "totp_credential"):
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {OWNER}")
