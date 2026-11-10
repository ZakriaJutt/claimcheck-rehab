"""B1 baseline: core tables, row-level security, append-only grants, job-queue functions.

T-2.2.1, T-2.2.2, T-2.2.5, T-2.2.6. Every clinic-owned table gets its policy in this same file (R-05).

Revision ID: 202611110900
Revises:
"""

from alembic import op

revision = "202611110900"
down_revision = None
branch_labels = None
depends_on = None

APP_ROLE = "claimcheck_app"

TABLES_SQL = r"""
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE FUNCTION cc_current_clinic() RETURNS uuid
LANGUAGE sql STABLE AS $$ SELECT nullif(current_setting('app.clinic_id', true), '')::uuid $$;

CREATE TABLE clinic (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  name text NOT NULL,
  location_label text NOT NULL,
  status text NOT NULL DEFAULT 'onboarding',
  pilot_started_on date,
  audit_report_sent_on date,
  timezone text NOT NULL DEFAULT 'America/Vancouver',
  payers text[] NOT NULL,
  imports_paused_at timestamptz,
  CONSTRAINT clinic_status_check CHECK (status IN ('onboarding','audit_only','pilot','active','closed'))
);

CREATE TABLE app_user (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  clinic_id uuid REFERENCES clinic(id),
  email citext NOT NULL UNIQUE,
  password_hash text NOT NULL,
  role text NOT NULL,
  disabled_at timestamptz,
  CONSTRAINT app_user_role_check CHECK (role IN ('owner','staff','operator')),
  CONSTRAINT app_user_operator_check CHECK ((role = 'operator') = (clinic_id IS NULL))
);

CREATE TABLE session (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  user_id uuid NOT NULL REFERENCES app_user(id),
  token_hash text NOT NULL UNIQUE,
  mfa_passed boolean NOT NULL DEFAULT false,
  last_seen_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz
);

CREATE TABLE export_profile (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  report text NOT NULL,
  version integer NOT NULL,
  header_map jsonb NOT NULL,
  required text[] NOT NULL,
  published_at timestamptz,
  CONSTRAINT export_profile_report_check CHECK (report IN ('sales','policies')),
  CONSTRAINT export_profile_report_version_key UNIQUE (report, version)
);

CREATE TABLE import_batch (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  clinic_id uuid NOT NULL REFERENCES clinic(id),
  created_by uuid NOT NULL REFERENCES app_user(id),
  content_hash text NOT NULL,
  export_date date NOT NULL,
  profile_sales_id uuid NOT NULL REFERENCES export_profile(id),
  profile_policies_id uuid NOT NULL REFERENCES export_profile(id),
  status text NOT NULL DEFAULT 'receiving',
  rows_received integer NOT NULL DEFAULT 0,
  rows_accepted integer NOT NULL DEFAULT 0,
  rows_rejected integer NOT NULL DEFAULT 0,
  rows_duplicate integer NOT NULL DEFAULT 0,
  expected_rows integer,
  correlation_id uuid NOT NULL,
  completed_at timestamptz,
  CONSTRAINT import_batch_status_check CHECK
    (status IN ('receiving','processing','completed','completed_with_rejects','failed','rejected_guard')),
  CONSTRAINT import_batch_counts_check CHECK
    (status NOT IN ('completed','completed_with_rejects')
     OR rows_received = rows_accepted + rows_rejected + rows_duplicate),
  CONSTRAINT import_batch_clinic_id_content_hash_key UNIQUE (clinic_id, content_hash)
);
CREATE INDEX ix_import_batch_clinic_created ON import_batch (clinic_id, created_at DESC);

CREATE TABLE import_row (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  clinic_id uuid NOT NULL REFERENCES clinic(id),
  batch_id uuid NOT NULL REFERENCES import_batch(id) ON DELETE CASCADE,
  row_no integer NOT NULL,
  kind text NOT NULL,
  payload jsonb NOT NULL,
  reject_reason text,
  CONSTRAINT import_row_kind_check CHECK (kind IN ('visit','claim')),
  CONSTRAINT import_row_batch_id_kind_row_no_key UNIQUE (batch_id, kind, row_no)
);

CREATE TABLE claim (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  clinic_id uuid NOT NULL REFERENCES clinic(id),
  claim_token varchar(32) NOT NULL,
  payer text NOT NULL,
  policy_status text,
  end_date date,
  treatments_count integer,
  policy_max integer,
  next_appointment_date date,
  date_of_event date,
  last_batch_id uuid NOT NULL REFERENCES import_batch(id),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT claim_payer_check CHECK (payer IN ('ICBC','WSBC','OTHER')),
  CONSTRAINT claim_token_format_check CHECK (claim_token ~ '^[0-9a-f]{32}$'),
  CONSTRAINT claim_clinic_id_claim_token_payer_key UNIQUE (clinic_id, claim_token, payer)
);

CREATE TABLE visit (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  clinic_id uuid NOT NULL REFERENCES clinic(id),
  invoice_ref text NOT NULL,
  line_no integer NOT NULL DEFAULT 1,
  claim_id uuid REFERENCES claim(id),
  payer text NOT NULL,
  discipline text NOT NULL,
  date_of_service date NOT NULL,
  billing_code text NOT NULL,
  amount_invoiced numeric(10,2) NOT NULL,
  amount_paid numeric(10,2) NOT NULL DEFAULT 0,
  submission_state text NOT NULL,
  state_date date,
  first_rejected_on date,
  first_seen_batch_id uuid NOT NULL REFERENCES import_batch(id),
  first_seen_export_date date NOT NULL,
  last_batch_id uuid NOT NULL REFERENCES import_batch(id),
  last_export_date date NOT NULL,
  check_status text,
  check_reason text,
  CONSTRAINT visit_payer_check CHECK (payer IN ('ICBC','WSBC','OTHER')),
  CONSTRAINT visit_discipline_check CHECK (discipline IN ('physiotherapy','support','other')),
  CONSTRAINT visit_amount_invoiced_check CHECK (amount_invoiced >= 0),
  CONSTRAINT visit_amount_paid_check CHECK (amount_paid >= 0),
  CONSTRAINT visit_submission_state_check CHECK
    (submission_state IN ('unsubmitted','submitted','rejected','partly_paid','paid','unknown')),
  CONSTRAINT visit_check_status_check CHECK
    (check_status IS NULL OR check_status IN ('in_scope','could_not_check','no_rules_applied')),
  CONSTRAINT visit_clinic_id_invoice_ref_line_no_key UNIQUE (clinic_id, invoice_ref, line_no)
);
CREATE INDEX ix_visit_eval ON visit (clinic_id, payer, submission_state, date_of_service);
CREATE INDEX ix_visit_claim ON visit (clinic_id, claim_id, date_of_service);

CREATE TABLE visit_snapshot (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  clinic_id uuid NOT NULL REFERENCES clinic(id),
  visit_id uuid NOT NULL REFERENCES visit(id),
  batch_id uuid NOT NULL REFERENCES import_batch(id),
  export_date date NOT NULL,
  submission_state text NOT NULL,
  amount_invoiced numeric(10,2) NOT NULL,
  amount_paid numeric(10,2) NOT NULL,
  state_date date,
  CONSTRAINT visit_snapshot_visit_id_batch_id_key UNIQUE (visit_id, batch_id)
);
CREATE INDEX ix_visit_snapshot_visit_export ON visit_snapshot (visit_id, export_date);

CREATE TABLE rule_version (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  rule_code text NOT NULL,
  version integer NOT NULL,
  effective_from date NOT NULL,
  effective_to date,
  params jsonb NOT NULL,
  source_citation text NOT NULL,
  source_id text NOT NULL,
  status text NOT NULL DEFAULT 'draft',
  fixtures_passed_at timestamptz,
  published_by uuid,
  published_at timestamptz,
  CONSTRAINT rule_version_status_check CHECK (status IN ('draft','published','superseded')),
  CONSTRAINT rule_version_range_check CHECK (effective_to IS NULL OR effective_to >= effective_from),
  CONSTRAINT rule_version_fixtures_check CHECK (status <> 'published' OR fixtures_passed_at IS NOT NULL),
  CONSTRAINT rule_version_rule_code_version_key UNIQUE (rule_code, version),
  CONSTRAINT rule_version_no_overlap EXCLUDE USING gist
    (rule_code WITH =, daterange(effective_from, effective_to, '[]') WITH &&) WHERE (status = 'published')
);

CREATE TABLE evaluation_run (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  clinic_id uuid NOT NULL REFERENCES clinic(id),
  local_date date NOT NULL,
  rule_set_hash text NOT NULL,
  trigger text NOT NULL,
  status text NOT NULL,
  correlation_id uuid NOT NULL,
  finished_at timestamptz,
  CONSTRAINT evaluation_run_trigger_check CHECK (trigger IN ('import','daily','rule_publish')),
  CONSTRAINT evaluation_run_status_check CHECK (status IN ('running','succeeded','failed')),
  CONSTRAINT evaluation_run_unique_key UNIQUE (clinic_id, local_date, rule_set_hash, trigger)
);

CREATE TABLE finding (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  clinic_id uuid NOT NULL REFERENCES clinic(id),
  visit_id uuid REFERENCES visit(id),
  claim_id uuid REFERENCES claim(id),
  rule_code text NOT NULL,
  rule_version_id uuid REFERENCES rule_version(id),
  outcome text NOT NULL,
  reason_code text,
  limit_date date,
  submit_by date,
  evaluation_run_id uuid NOT NULL REFERENCES evaluation_run(id),
  evaluated_on date NOT NULL,
  CONSTRAINT finding_outcome_check CHECK (outcome IN ('flag','clear','not_evaluated')),
  CONSTRAINT finding_target_check CHECK ((visit_id IS NULL) <> (claim_id IS NULL)),
  CONSTRAINT finding_reason_check CHECK (outcome <> 'not_evaluated' OR reason_code IS NOT NULL),
  CONSTRAINT finding_version_check CHECK
    (rule_version_id IS NOT NULL OR (outcome = 'not_evaluated' AND reason_code = 'no_rule_version'))
);
CREATE UNIQUE INDEX ux_finding_visit_rule ON finding (visit_id, rule_code) WHERE visit_id IS NOT NULL;
CREATE UNIQUE INDEX ux_finding_claim_rule ON finding (claim_id, rule_code) WHERE claim_id IS NOT NULL;
CREATE INDEX ix_finding_rule_outcome ON finding (clinic_id, rule_code, outcome);

CREATE TABLE item (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  clinic_id uuid NOT NULL REFERENCES clinic(id),
  visit_id uuid REFERENCES visit(id),
  claim_id uuid REFERENCES claim(id),
  rule_code text NOT NULL,
  money_class text NOT NULL,
  amount numeric(10,2),
  limit_date date,
  status text NOT NULL DEFAULT 'open',
  first_flagged_on date NOT NULL,
  reached_near_limit_on date,
  class_at_first_flag text NOT NULL,
  paid_after_flag numeric(10,2) NOT NULL DEFAULT 0,
  version integer NOT NULL DEFAULT 1,
  CONSTRAINT item_money_class_check CHECK
    (money_class IN ('permanent_certain','permanent_discretionary','delayed_cash','admin_time','warning')),
  CONSTRAINT item_status_check CHECK
    (status IN ('open','awaiting_confirmation','confirmed','auto_cleared','written_off','dismissed')),
  CONSTRAINT item_target_check CHECK ((visit_id IS NULL) <> (claim_id IS NULL)),
  CONSTRAINT item_amount_class_check CHECK (money_class NOT IN ('admin_time','warning') OR amount IS NULL)
);
CREATE UNIQUE INDEX ux_item_visit_rule ON item (clinic_id, visit_id, rule_code) WHERE visit_id IS NOT NULL;
CREATE UNIQUE INDEX ux_item_claim_rule ON item (clinic_id, claim_id, rule_code) WHERE claim_id IS NOT NULL;
CREATE INDEX ix_item_list ON item (clinic_id, status, limit_date);
CREATE INDEX ix_item_near_limit_paid ON item (clinic_id, reached_near_limit_on) WHERE paid_after_flag > 0;

-- MH-08 (b): first_flagged_on, class_at_first_flag and reached_near_limit_on are written once.
CREATE FUNCTION cc_item_write_once() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.first_flagged_on IS DISTINCT FROM OLD.first_flagged_on
     OR NEW.class_at_first_flag IS DISTINCT FROM OLD.class_at_first_flag
     OR (OLD.reached_near_limit_on IS NOT NULL
         AND NEW.reached_near_limit_on IS DISTINCT FROM OLD.reached_near_limit_on) THEN
    RAISE EXCEPTION 'write-once item field changed' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER item_write_once BEFORE UPDATE ON item FOR EACH ROW EXECUTE FUNCTION cc_item_write_once();

CREATE TABLE item_event (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  clinic_id uuid NOT NULL REFERENCES clinic(id),
  item_id uuid NOT NULL REFERENCES item(id),
  actor_user_id uuid REFERENCES app_user(id),
  kind text NOT NULL,
  outcome text,
  reason_code text,
  idempotency_key text NOT NULL,
  CONSTRAINT item_event_kind_check CHECK
    (kind IN ('flagged','class_changed','outcome','undone','reopened','confirmed','auto_cleared')),
  CONSTRAINT item_event_outcome_check CHECK
    (outcome IS NULL OR outcome IN ('submitted','verified_in_portal','portal_not_received',
     'corrected_resubmitted','treatment_plan_requested','written_off','not_an_error')),
  CONSTRAINT item_event_reason_check CHECK
    (reason_code IS NULL OR reason_code IN
     ('already_paid','payer_approved','duplicate_row','rule_wrong','not_our_claim','other')),
  CONSTRAINT item_event_item_id_idempotency_key_key UNIQUE (item_id, idempotency_key)
);

CREATE TABLE job (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  clinic_id uuid REFERENCES clinic(id),
  kind text NOT NULL,
  idempotency_key text NOT NULL UNIQUE,
  status text NOT NULL DEFAULT 'queued',
  attempt integer NOT NULL DEFAULT 0,
  max_attempts integer NOT NULL DEFAULT 3,
  run_after timestamptz NOT NULL DEFAULT now(),
  lease_token uuid,
  lease_expires_at timestamptz,
  correlation_id uuid NOT NULL,
  last_error_code text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  finished_at timestamptz,
  CONSTRAINT job_status_check CHECK (status IN ('queued','running','succeeded','failed','dead'))
);
CREATE INDEX ix_job_queued ON job (status, run_after) WHERE status = 'queued';
CREATE INDEX ix_job_running ON job (status, lease_expires_at) WHERE status = 'running';

CREATE TABLE audit_event (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  clinic_id uuid,
  actor_user_id uuid,
  action text NOT NULL,
  object_type text,
  object_id uuid,
  outcome text NOT NULL,
  correlation_id uuid NOT NULL,
  ip_hash text,
  meta jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX ix_audit_event_clinic_created ON audit_event (clinic_id, created_at DESC);
"""

RLS_TABLES = (
    "app_user", "import_batch", "import_row", "claim", "visit", "visit_snapshot", "evaluation_run",
    "finding", "item", "item_event", "job",
)

FUNCTIONS_SQL = r"""
-- Session lookup before a clinic is known (no direct grant on session to the app role).
CREATE FUNCTION cc_session_principal(p_token_hash text, p_idle_minutes integer)
RETURNS TABLE(user_id uuid, clinic_id uuid, role text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  RETURN QUERY
  UPDATE session s SET last_seen_at = now()
  FROM app_user u
  WHERE s.token_hash = p_token_hash AND u.id = s.user_id
    AND s.revoked_at IS NULL AND s.mfa_passed AND s.expires_at > now()
    AND s.last_seen_at > now() - make_interval(mins => p_idle_minutes)
    AND u.disabled_at IS NULL
  RETURNING u.id, u.clinic_id, u.role;
END $$;

-- Job queue: claim one due job with a lease (FOR UPDATE SKIP LOCKED), across clinics.
CREATE FUNCTION cc_job_claim(p_lease uuid, p_lease_seconds integer, p_kinds text[])
RETURNS SETOF job
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
  UPDATE job SET status = 'running', attempt = attempt + 1, lease_token = p_lease,
         lease_expires_at = now() + make_interval(secs => p_lease_seconds)
  WHERE id = (
    SELECT id FROM job
    WHERE status = 'queued' AND run_after <= now() AND (p_kinds IS NULL OR kind = ANY(p_kinds))
    ORDER BY run_after, created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1)
  RETURNING *;
$$;

-- Completion is guarded by the lease: a late or duplicate completion updates zero rows (R-01).
CREATE FUNCTION cc_job_complete(p_job uuid, p_lease uuid, p_ok boolean, p_error text, p_retryable boolean)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer;
BEGIN
  IF p_ok THEN
    UPDATE job SET status = 'succeeded', finished_at = now(), lease_token = NULL, lease_expires_at = NULL
    WHERE id = p_job AND status = 'running' AND lease_token = p_lease;
  ELSE
    UPDATE job SET
      status = CASE WHEN p_retryable AND attempt < max_attempts THEN 'queued'
                    WHEN p_retryable THEN 'dead' ELSE 'failed' END,
      run_after = now() + CASE attempt WHEN 1 THEN interval '30 seconds' WHEN 2 THEN interval '2 minutes'
                                       ELSE interval '10 minutes' END,
      last_error_code = p_error, lease_token = NULL, lease_expires_at = NULL,
      finished_at = CASE WHEN p_retryable AND attempt < max_attempts THEN NULL ELSE now() END
    WHERE id = p_job AND status = 'running' AND lease_token = p_lease;
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END $$;

-- Lease-expiry sweep: a crashed worker's job is retried (or dead after max attempts).
CREATE FUNCTION cc_job_expire_leases() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer;
BEGIN
  UPDATE job SET status = CASE WHEN attempt < max_attempts THEN 'queued' ELSE 'dead' END,
                 last_error_code = 'lease_expired', lease_token = NULL, lease_expires_at = NULL,
                 run_after = now()
  WHERE status = 'running' AND lease_expires_at < now();
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END $$;

-- Scheduler: one job per non-closed clinic, idempotent on the key.
CREATE FUNCTION cc_enqueue_per_clinic(p_kind text, p_key_suffix text, p_payload jsonb, p_correlation uuid)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer;
BEGIN
  INSERT INTO job (clinic_id, kind, idempotency_key, correlation_id, payload)
  SELECT c.id, p_kind, p_kind || ':' || c.id || ':' || p_key_suffix, p_correlation, p_payload
  FROM clinic c WHERE c.status <> 'closed'
  ON CONFLICT (idempotency_key) DO NOTHING;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END $$;
"""


def upgrade() -> None:
    op.execute(TABLES_SQL)
    # Row-level security: every clinic-owned table, same file (R-05). FORCE so the owner is bound too.
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant ON {table} "
            "USING (clinic_id = cc_current_clinic()) WITH CHECK (clinic_id = cc_current_clinic())"
        )
    op.execute("ALTER TABLE clinic ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE clinic FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY clinic_tenant ON clinic USING (id = cc_current_clinic()) "
               "WITH CHECK (id = cc_current_clinic())")
    op.execute("ALTER TABLE audit_event ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_event FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY audit_event_read ON audit_event FOR SELECT USING (clinic_id = cc_current_clinic())")
    op.execute("CREATE POLICY audit_event_insert ON audit_event FOR INSERT "
               "WITH CHECK (clinic_id IS NULL OR clinic_id = cc_current_clinic())")

    op.execute(FUNCTIONS_SQL)

    # Grants for the application role. Append-only tables get INSERT and SELECT only (schema.md 8).
    r = APP_ROLE
    op.execute(f"GRANT USAGE ON SCHEMA public TO {r}")
    op.execute(f"GRANT SELECT, UPDATE ON clinic TO {r}")
    op.execute(f"GRANT SELECT ON app_user, export_profile, rule_version, alembic_version TO {r}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON import_batch, claim, visit, evaluation_run, finding, item TO {r}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON import_row TO {r}")
    op.execute(f"GRANT SELECT, INSERT ON visit_snapshot, item_event, audit_event TO {r}")
    op.execute(f"GRANT SELECT, INSERT ON job TO {r}")
    for fn in (
        "cc_current_clinic()",
        "cc_session_principal(text, integer)",
        "cc_job_claim(uuid, integer, text[])",
        "cc_job_complete(uuid, uuid, boolean, text, boolean)",
        "cc_job_expire_leases()",
        "cc_enqueue_per_clinic(text, text, jsonb, uuid)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO {r}")


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS cc_enqueue_per_clinic(text, text, jsonb, uuid), cc_job_expire_leases(), "
        "cc_job_complete(uuid, uuid, boolean, text, boolean), cc_job_claim(uuid, integer, text[]), "
        "cc_session_principal(text, integer)"
    )
    for table in (
        "audit_event", "job", "item_event", "item", "finding", "evaluation_run", "rule_version",
        "visit_snapshot", "visit", "claim", "import_row", "import_batch", "export_profile", "session",
        "app_user", "clinic",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS cc_item_write_once(), cc_current_clinic()")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}")
