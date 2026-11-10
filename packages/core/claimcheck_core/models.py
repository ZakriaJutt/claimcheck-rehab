"""ORM declarations. Must match the migrations exactly (R-08); scripts/check_migrations.py compares them.

B1 subset of schema.md section 3: the tables the import, rule engine, list and job core need.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID, ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

MONEY = Numeric(10, 2)


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _clinic_fk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("clinic.id"), nullable=False)


class Clinic(Base):
    __tablename__ = "clinic"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    location_label: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'onboarding'"))
    pilot_started_on: Mapped[date | None] = mapped_column(Date)
    audit_report_sent_on: Mapped[date | None] = mapped_column(Date)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'America/Vancouver'"))
    payers: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    imports_paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "status IN ('onboarding','audit_only','pilot','active','closed')", name="clinic_status_check"
        ),
    )


class AppUser(Base):
    __tablename__ = "app_user"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clinic.id"))
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("role IN ('owner','staff','operator')", name="app_user_role_check"),
        CheckConstraint("(role = 'operator') = (clinic_id IS NULL)", name="app_user_operator_check"),
    )


class UserSession(Base):
    __tablename__ = "session"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    mfa_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExportProfile(Base):
    __tablename__ = "export_profile"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    report: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    header_map: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    required: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("report IN ('sales','policies')", name="export_profile_report_check"),
        UniqueConstraint("report", "version", name="export_profile_report_version_key"),
    )


class ImportBatch(Base):
    __tablename__ = "import_batch"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    clinic_id: Mapped[uuid.UUID] = _clinic_fk()
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    export_date: Mapped[date] = mapped_column(Date, nullable=False)
    profile_sales_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("export_profile.id"), nullable=False
    )
    profile_policies_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("export_profile.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'receiving'"))
    rows_received: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    rows_accepted: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    rows_rejected: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    rows_duplicate: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    expected_rows: Mapped[int | None] = mapped_column(Integer)
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "status IN ('receiving','processing','completed','completed_with_rejects','failed','rejected_guard')",
            name="import_batch_status_check",
        ),
        CheckConstraint(
            "status NOT IN ('completed','completed_with_rejects') "
            "OR rows_received = rows_accepted + rows_rejected + rows_duplicate",
            name="import_batch_counts_check",
        ),
        UniqueConstraint("clinic_id", "content_hash", name="import_batch_clinic_id_content_hash_key"),
        Index("ix_import_batch_clinic_created", "clinic_id", literal_column("created_at DESC")),
    )


class ImportRow(Base):
    __tablename__ = "import_row"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    clinic_id: Mapped[uuid.UUID] = _clinic_fk()
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_batch.id", ondelete="CASCADE"), nullable=False
    )
    row_no: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reject_reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("kind IN ('visit','claim')", name="import_row_kind_check"),
        UniqueConstraint("batch_id", "kind", "row_no", name="import_row_batch_id_kind_row_no_key"),
    )


class Claim(Base):
    __tablename__ = "claim"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    clinic_id: Mapped[uuid.UUID] = _clinic_fk()
    claim_token: Mapped[str] = mapped_column(String(32), nullable=False)
    payer: Mapped[str] = mapped_column(Text, nullable=False)
    policy_status: Mapped[str | None] = mapped_column(Text)
    end_date: Mapped[date | None] = mapped_column(Date)
    treatments_count: Mapped[int | None] = mapped_column(Integer)
    policy_max: Mapped[int | None] = mapped_column(Integer)
    next_appointment_date: Mapped[date | None] = mapped_column(Date)
    date_of_event: Mapped[date | None] = mapped_column(Date)
    last_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_batch.id"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        CheckConstraint("payer IN ('ICBC','WSBC','OTHER')", name="claim_payer_check"),
        CheckConstraint("claim_token ~ '^[0-9a-f]{32}$'", name="claim_token_format_check"),
        UniqueConstraint("clinic_id", "claim_token", "payer", name="claim_clinic_id_claim_token_payer_key"),
    )


class Visit(Base):
    __tablename__ = "visit"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    clinic_id: Mapped[uuid.UUID] = _clinic_fk()
    invoice_ref: Mapped[str] = mapped_column(Text, nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    claim_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("claim.id"))
    payer: Mapped[str] = mapped_column(Text, nullable=False)
    discipline: Mapped[str] = mapped_column(Text, nullable=False)
    date_of_service: Mapped[date] = mapped_column(Date, nullable=False)
    billing_code: Mapped[str] = mapped_column(Text, nullable=False)
    amount_invoiced: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(MONEY, nullable=False, server_default=text("0"))
    submission_state: Mapped[str] = mapped_column(Text, nullable=False)
    state_date: Mapped[date | None] = mapped_column(Date)
    first_rejected_on: Mapped[date | None] = mapped_column(Date)
    first_seen_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_batch.id"), nullable=False
    )
    first_seen_export_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_batch.id"), nullable=False
    )
    last_export_date: Mapped[date] = mapped_column(Date, nullable=False)
    check_status: Mapped[str | None] = mapped_column(Text)
    check_reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("payer IN ('ICBC','WSBC','OTHER')", name="visit_payer_check"),
        CheckConstraint("discipline IN ('physiotherapy','support','other')", name="visit_discipline_check"),
        CheckConstraint("amount_invoiced >= 0", name="visit_amount_invoiced_check"),
        CheckConstraint("amount_paid >= 0", name="visit_amount_paid_check"),
        CheckConstraint(
            "submission_state IN ('unsubmitted','submitted','rejected','partly_paid','paid','unknown')",
            name="visit_submission_state_check",
        ),
        CheckConstraint(
            "check_status IS NULL OR check_status IN ('in_scope','could_not_check','no_rules_applied')",
            name="visit_check_status_check",
        ),
        UniqueConstraint("clinic_id", "invoice_ref", "line_no", name="visit_clinic_id_invoice_ref_line_no_key"),
        Index("ix_visit_eval", "clinic_id", "payer", "submission_state", "date_of_service"),
        Index("ix_visit_claim", "clinic_id", "claim_id", "date_of_service"),
    )


class VisitSnapshot(Base):
    __tablename__ = "visit_snapshot"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    clinic_id: Mapped[uuid.UUID] = _clinic_fk()
    visit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("visit.id"), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("import_batch.id"), nullable=False)
    export_date: Mapped[date] = mapped_column(Date, nullable=False)
    submission_state: Mapped[str] = mapped_column(Text, nullable=False)
    amount_invoiced: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    state_date: Mapped[date | None] = mapped_column(Date)
    __table_args__ = (
        UniqueConstraint("visit_id", "batch_id", name="visit_snapshot_visit_id_batch_id_key"),
        Index("ix_visit_snapshot_visit_export", "visit_id", "export_date"),
    )


class RuleVersion(Base):
    __tablename__ = "rule_version"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    rule_code: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_citation: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    fixtures_passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("status IN ('draft','published','superseded')", name="rule_version_status_check"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="rule_version_range_check"
        ),
        CheckConstraint(
            "status <> 'published' OR fixtures_passed_at IS NOT NULL", name="rule_version_fixtures_check"
        ),
        UniqueConstraint("rule_code", "version", name="rule_version_rule_code_version_key"),
        ExcludeConstraint(
            (literal_column("rule_code"), "="),
            (literal_column("daterange(effective_from, effective_to, '[]')"), "&&"),
            where=text("status = 'published'"),
            using="gist",
            name="rule_version_no_overlap",
        ),
    )


class EvaluationRun(Base):
    __tablename__ = "evaluation_run"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    clinic_id: Mapped[uuid.UUID] = _clinic_fk()
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    rule_set_hash: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("trigger IN ('import','daily','rule_publish')", name="evaluation_run_trigger_check"),
        CheckConstraint("status IN ('running','succeeded','failed')", name="evaluation_run_status_check"),
        UniqueConstraint(
            "clinic_id", "local_date", "rule_set_hash", "trigger", name="evaluation_run_unique_key"
        ),
    )


class Finding(Base):
    __tablename__ = "finding"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    clinic_id: Mapped[uuid.UUID] = _clinic_fk()
    visit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("visit.id"))
    claim_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("claim.id"))
    rule_code: Mapped[str] = mapped_column(Text, nullable=False)
    rule_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rule_version.id"))
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str | None] = mapped_column(Text)
    limit_date: Mapped[date | None] = mapped_column(Date)
    submit_by: Mapped[date | None] = mapped_column(Date)
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_run.id"), nullable=False
    )
    evaluated_on: Mapped[date] = mapped_column(Date, nullable=False)
    __table_args__ = (
        CheckConstraint("outcome IN ('flag','clear','not_evaluated')", name="finding_outcome_check"),
        CheckConstraint("(visit_id IS NULL) <> (claim_id IS NULL)", name="finding_target_check"),
        CheckConstraint("outcome <> 'not_evaluated' OR reason_code IS NOT NULL", name="finding_reason_check"),
        CheckConstraint(
            "rule_version_id IS NOT NULL OR (outcome = 'not_evaluated' AND reason_code = 'no_rule_version')",
            name="finding_version_check",
        ),
        Index(
            "ux_finding_visit_rule", "visit_id", "rule_code", unique=True,
            postgresql_where=text("visit_id IS NOT NULL"),
        ),
        Index(
            "ux_finding_claim_rule", "claim_id", "rule_code", unique=True,
            postgresql_where=text("claim_id IS NOT NULL"),
        ),
        Index("ix_finding_rule_outcome", "clinic_id", "rule_code", "outcome"),
    )


class Item(Base):
    __tablename__ = "item"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    clinic_id: Mapped[uuid.UUID] = _clinic_fk()
    visit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("visit.id"))
    claim_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("claim.id"))
    rule_code: Mapped[str] = mapped_column(Text, nullable=False)
    money_class: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(MONEY)
    limit_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    first_flagged_on: Mapped[date] = mapped_column(Date, nullable=False)
    reached_near_limit_on: Mapped[date | None] = mapped_column(Date)
    class_at_first_flag: Mapped[str] = mapped_column(Text, nullable=False)
    paid_after_flag: Mapped[Decimal] = mapped_column(MONEY, nullable=False, server_default=text("0"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    __table_args__ = (
        CheckConstraint(
            "money_class IN ('permanent_certain','permanent_discretionary','delayed_cash','admin_time','warning')",
            name="item_money_class_check",
        ),
        CheckConstraint(
            "status IN ('open','awaiting_confirmation','confirmed','auto_cleared','written_off','dismissed')",
            name="item_status_check",
        ),
        CheckConstraint("(visit_id IS NULL) <> (claim_id IS NULL)", name="item_target_check"),
        CheckConstraint(
            "money_class NOT IN ('admin_time','warning') OR amount IS NULL", name="item_amount_class_check"
        ),
        Index(
            "ux_item_visit_rule", "clinic_id", "visit_id", "rule_code", unique=True,
            postgresql_where=text("visit_id IS NOT NULL"),
        ),
        Index(
            "ux_item_claim_rule", "clinic_id", "claim_id", "rule_code", unique=True,
            postgresql_where=text("claim_id IS NOT NULL"),
        ),
        Index("ix_item_list", "clinic_id", "status", "limit_date"),
        Index(
            "ix_item_near_limit_paid", "clinic_id", "reached_near_limit_on",
            postgresql_where=text("paid_after_flag > 0"),
        ),
    )


class ItemEvent(Base):
    __tablename__ = "item_event"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    clinic_id: Mapped[uuid.UUID] = _clinic_fk()
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("item.id"), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id"))
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str | None] = mapped_column(Text)
    reason_code: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "kind IN ('flagged','class_changed','outcome','undone','reopened','confirmed','auto_cleared')",
            name="item_event_kind_check",
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('submitted','verified_in_portal','portal_not_received',"
            "'corrected_resubmitted','treatment_plan_requested','written_off','not_an_error')",
            name="item_event_outcome_check",
        ),
        CheckConstraint(
            "reason_code IS NULL OR reason_code IN "
            "('already_paid','payer_approved','duplicate_row','rule_wrong','not_our_claim','other')",
            name="item_event_reason_check",
        ),
        UniqueConstraint("item_id", "idempotency_key", name="item_event_item_id_idempotency_key_key"),
    )


class Job(Base):
    __tablename__ = "job"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clinic.id"))
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'queued'"))
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("3"))
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("status IN ('queued','running','succeeded','failed','dead')", name="job_status_check"),
        Index("ix_job_queued", "status", "run_after", postgresql_where=text("status = 'queued'")),
        Index("ix_job_running", "status", "lease_expires_at", postgresql_where=text("status = 'running'")),
    )


class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime] = _created()
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str | None] = mapped_column(Text)
    object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ip_hash: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    __table_args__ = (Index("ix_audit_event_clinic_created", "clinic_id", literal_column("created_at DESC")),)


# Tables that carry clinic_id and therefore must have a row-level-security policy (R-05).
CLINIC_OWNED_TABLES = (
    "app_user", "import_batch", "import_row", "claim", "visit", "visit_snapshot", "evaluation_run",
    "finding", "item", "item_event", "job", "audit_event",
)
