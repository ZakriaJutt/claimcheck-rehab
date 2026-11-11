# AGENTS.md — ClaimCheck Rehab

Canonical instructions for any agent or developer working in this repository. [CLAUDE.md](CLAUDE.md) adds product-specific guidance and defers to this file.

**State of the repository (2026-11-11, branch `feat/b2-local-auth`):** the ten planning documents, the B1 build (foundation and deterministic core) and B2 (sign-in with password and TOTP, recovery codes, invitations, password reset, sessions, anti-forgery, rate limits, email through SMTP to the local Mailpit, the minimised import payload in the local MinIO object store under AD-11). The owner authorised implementation on 2026-11-11, before the Phase 0 stop-rule decision (T-0.4.3) had been taken; that departure is recorded in [verification-report-fixing.md](verification-report-fixing.md#b1-implementation-record-2026-11-11) and the decision text in Decision.md is unchanged. Implemented: `packages/core`, `packages/minimiser`, `apps/api`, `apps/worker`, migrations, tests. Not implemented: `apps/web`, the weekly email, deletion and export (MH-11), lost-factor re-enrolment, password change while signed in, operator sign-in, deployment. Commands marked "exists" in [Commands (B1, B2)](#commands-b1-b2) have been run; every other command named anywhere is still **proposed**.

## Reading order

1. [Decision.md](Decision.md) — whether to build at all; labels; payer rules PR-nn; sources SRC-nn.
2. [PRD.md](PRD.md) — must-haves MH-nn, non-goals, metrics M-nn, HCF-1 and HCF-2.
3. [TRD.md](TRD.md) — architecture, rule catalogue, APIs, decisions AD-nn.
4. [schema.md](schema.md) — the 16 fields, tables, permissions, retention, migrations.
5. [App-flow.md](App-flow.md) and [design.md](design.md) — screens S-nn, states, copy.
6. [execution-plan.md](execution-plan.md) — tasks T-p.m.t, tests.
7. [verification-report-fixing.md](verification-report-fixing.md) — traceability, risks R-nn, findings F-nnn.

## Sources of truth

| Subject | File |
|---|---|
| Labels, sources, payer rules, economics, stop rule, go-to-market | Decision.md |
| Requirements, roles, metrics, highest-consequence failure | PRD.md |
| Rule logic (ICBC-nn, WSBC-nn), APIs, jobs, security targets | TRD.md |
| Fields a clinic may send; tables; permissions; retention | schema.md |
| Routes and screen behaviour | App-flow.md |
| Visual and copy decisions (DD-nn), accessibility map | design.md |
| Tasks, estimates, tests | execution-plan.md |
| Risks, traceability, findings, self-check | verification-report-fixing.md |

State a fact once, in its home file; elsewhere cite the ID.

## What to update when something changes

| Change | Update |
|---|---|
| A requirement | PRD (MH row) → verification (matrix row) → execution-plan (task, test) → App-flow or TRD if behaviour changes |
| A screen or route | App-flow (inventory, screen, navigation diagram) → design (if principal screen, accessibility map) → verification matrix |
| A permission or role | schema (permission table, RLS note) → PRD roles → App-flow roles column → permission tests in execution-plan |
| A table, field or index | schema (diagram, dictionary, index table, retention) → TRD if an API changes → migration task |
| A field sent by the clinic | schema section 2 **first** → Decision section 6 → PRD MH-01 → TRD guard → the data agreement (T-0.1.3). Adding a field needs the owner's written approval |
| A payer rule or fee | Decision 4.1 (PR row, source, date) → TRD rule table → fixtures (T-1.1.1) → S-13 log entry |
| An operating assumption (price, rate, cost, pool) | Decision (inputs, then every derived figure, ramp tables, stop-rule probabilities) → PRD targets → re-run the arithmetic and record it in the SC log |
| A risk disposition | verification register only |

## Product boundaries

- Read-only helper beside Jane. Never write to Jane, Teleplan, HCPIR or HCPP.
- Physiotherapy, ICBC and WorkSafeBC only, until other payer documents are read and cited.
- No AI function. No cache. No file storage except the minimised import payload under AD-11 (B2, owner approval pending), reached only through `storage.ClinicObjects`. Adding any other stored file, an AI function or a cache needs a new AD and a review of R-05, R-13, R-14 and R-16.
- No build task before T-0.4.3 records "go".

## Commands (B1, B2)

| Command | Status | What it does |
|---|---|---|
| `make venv` | exists | Python 3.12 virtual environment at `dev/.venv`; npm install in `packages/minimiser` |
| `make dev` / `make stop` | exists | `scripts/dev.sh`: checks PostgreSQL, migrates `claimcheck_dev`, runs the rule fixtures and only then publishes rules, starts the API on 8107 and the worker, checks `/healthz`, `/readyz` and the worker heartbeat; names the first unhealthy service. No web app on 3107 yet; no Redis (AD-05) |
| `make test` | exists | Unit (pytest), integration (pytest against real PostgreSQL `claimcheck_test`, schema dropped and re-migrated at session start; B2 suites also against Mailpit and MinIO, cleaning up their messages and objects), minimiser (Vitest) |
| `make test-clean` | exists | `make test` then `scripts/check_migrations.py` on the test database |
| `make lint`, `make typecheck` | exist | ruff and mypy (strict); eslint and tsc |
| `make check-migrations` | exists | Single head, ORM parity, forced RLS policy on every `clinic_id` table, invalid indexes |
| `scripts/publish_rules.py` | exists | Publishes export profile v1 and the rule catalogue; refuses without `--fixtures-passed`, and refuses when a stored version differs from the catalogue under the same number |
| `scripts/invite_owner.py` | exists (B2) | Operator: creates a clinic (or takes `--clinic-id`) and emails its first owner an invitation through SMTP; never prints the token |
| `make deploy`, `scripts/backfill_runner.py`, `scripts/seed_synthetic.py`, `scripts/restore_replay.py`, `scripts/phase0_links.sh`, `scripts/log_scan.py` | proposed | Not built in B1 |

Local values: databases `claimcheck_dev` / `claimcheck_test`; application role `claimcheck_app` and worker role `claimcheck_worker` (both NOSUPERUSER, NOBYPASSRLS; only the worker role may run the job-queue functions); non-login function owners `claimcheck_queue_owner` and `claimcheck_session_owner` (created by migrations); API port 8107; frontend port 3107 (reserved); Redis database 6 (reserved, unused). B2: function owners `claimcheck_auth_owner` (sign-in functions) as well; Mailpit SMTP 127.0.0.1:1025 (inbox http://127.0.0.1:8025); MinIO S3 API http://127.0.0.1:9000, region `us-east-1`, bucket `claimcheck-dev`. Credentials and the TOTP key live only in the git-ignored `.env.local`; `.env.example` lists the variable names. `make test` needs PostgreSQL, Mailpit and MinIO running (the two B2 suites skip when Mailpit or MinIO is down; the import tests need MinIO, because the worker stores each completed payload).

## Utilities index (search here before writing a helper, R-03)

| Need | Module (`packages/core/claimcheck_core`) |
|---|---|
| Settings, fail-fast on a missing variable | `settings.py` (`get_settings`, `load_settings`) |
| JSON logging, correlation ID, withheld keys | `logging.py` (`configure`, `get_logger`, `log_event`, `set_correlation_id`) |
| Calendar days in America/Vancouver | `dates.py` (`local_today`, `local_date_of`, `add_days`, `days_since`, `in_range`) |
| Money as `Decimal` to the cent | `money.py` (`cad`, `total`, `ZERO`) |
| Tenant transaction (`app.clinic_id`) | `tenancy.py` (`tenant_session`, `system_session`) — the only place that sets it |
| Database engine | `db.py` (`get_engine`, `make_engine`) |
| ORM models, list of clinic tables | `models.py` (`CLINIC_OWNED_TABLES`) |
| Job queue: enqueue, claim with lease, guarded completion, lease sweep | `jobs.py` |
| Audit events (counts and codes only) | `audit.py` (`write_audit`) |
| Operator alerts behind an interface | `alerts.py` (`Alerter`, `AuditAlerter`) |
| Import payload contract (16 fields + 2 ordinals) | `intake/contract.py` |
| Identifier guard checks (i)–(iv) | `intake/guard.py` (`check_rows`) |
| Batches: create, stage, finalize | `imports.py` |
| Daily stored-row scan | `identifier_scan.py` |
| Rule catalogue with effective dates and citations | `rules/catalogue.py` |
| Scope check and engine | `rules/engine.py` (`evaluate`, `scope_of`) |
| ICBC and WorkSafeBC rule functions, deadline arithmetic | `rules/payer_rules.py` (`submission_limit`, `wsbc_correction_limit`) |
| Item lifecycle (write-once near-limit date, class change, confirmation) | `items.py` (`next_item`) |
| Evaluation job, M-09 escapes, freshness | `evaluation.py` |
| Staff outcomes with `If-Match` and idempotency | `outcomes.py` |
| Band and cohort conversions; "nothing needs action" sentence | `measure.py` |
| Week-list counts that add up to rows received; could-not-check rows; summary rule | `lists.py` (`week_counts`, `summary_sentence`, `banner`) |
| Export profile v1 (placeholder headers `[A]`) | `profiles/jane_v1.json`, `seed.py` |
| Password policy, argon2id hashing, common-password list | `auth/passwords.py` (`policy_problem`, `hash_password`, `verify_password`) |
| TOTP (RFC 6238), sealed secrets, recovery codes | `auth/totp.py` (`match_step`, `SecretBox`, `new_recovery_codes`) |
| Sign-in, second factor, sign-out, reset, invitations, user removal, rate limits | `auth/service.py` (over the `cc_auth_*` functions) |
| Email (SMTP; Mailpit locally), invitation and reset messages | `mail.py` (`SmtpMailer`, `MemoryMailer`, `invite_mail`, `reset_mail`, `send_safely`) |
| Object store (S3 API; MinIO locally), clinic-bound keys | `storage.py` (`ClinicObjects`, `object_key`, `get_store`, `MemoryBlobStore`) |
| Stored import payload: archive, read, retention purge, clinic deletion | `payloads.py` |
| Audit event without a clinic | `audit.py` (`write_global_audit`) |
| Browser minimiser | `packages/minimiser/src` (`minimise`, `claimToken`, `contentHash`, `rowRequests`) |

## Architecture conventions (proposed)

- `apps/web` (Next.js), `apps/api` (FastAPI), `apps/worker`, `packages/core` (Python), `packages/minimiser` (TypeScript, browser).
- Apps import only the public interface of packages and never each other.
- Dates, money, tenancy, settings, logging and rules live in `packages/core`. Search there before writing a helper; do not create a second one (R-03).
- Date arithmetic is on local calendar dates in America/Vancouver; money is `numeric(10,2)`.
- A rule returns `flag`, `clear` or `not_evaluated(reason)`. `not_evaluated` is never a pass and never stops another rule. Only an in-scope visit with a recognised state and a loaded rule version can be `clear`.
- Every rule version, not only a fee, has an effective date range.
- Never ask a user to type a value the export should have supplied.

## Tenant safety

- Tenant = clinic location. Every clinic-owned table has `clinic_id` and a row-level-security policy in the same migration that creates it.
- Only the tenancy module sets `app.clinic_id`. The worker sets it from the job.
- Another clinic's object is a 404, with an audit event.
- The operator role reads no clinic rows without a live `support_grant`.
- Uniqueness is per clinic.

## Data handling

- Only the 16 fields in schema.md section 2 may reach the server. The server rejects anything else it can recognise; that check is not proof.
- Phase 0 files follow the Phase 0 data procedure in execution-plan.md: prepared at the clinic, never emailed.
- Fixtures are synthetic. Never copy a real export, invoice number, claim number or name into the repository, an issue, a log or a prompt.
- Logs carry IDs and counts only.

## Migrations

Linear Alembic history, single head; expand then contract; backfills separate, batched and resumable; `CREATE INDEX CONCURRENTLY` on populated tables with lock and statement timeouts; ORM parity checked in CI. Details: schema.md section 11.

## Tests

Write the fixture before the rule. Each rule needs a `flag`, a `clear`, a boundary-day and a `not_evaluated` case. Integration tests use real PostgreSQL. Test IDs and expected results: execution-plan.md.

## Git hygiene

Branch `type/T-x.y.z-short-slug`; one task per branch; delete on merge; never force-push a shared branch; never rewrite another person's unmerged work; every commit message cites an MH, T or R. Do not commit secrets, `.env` files, exports or generated data.

## Reporting completion accurately

- Say "specified" for documents, "implemented" only for code that exists, "verified" only with a named test or inspection and its result.
- A planned control is not compliance. Do not write "ASVS compliant" or "WCAG conformant".
- If a check was not run, write `Not run`.
- Report departures from the decision brief and unverifiable sources instead of smoothing them over.
- Record author checks as SC-nn; leave F-nnn to the independent reviewer.
