# AGENTS.md — ClaimCheck Rehab

Canonical instructions for any agent or developer working in this repository. [CLAUDE.md](CLAUDE.md) adds product-specific guidance and defers to this file.

**State of the repository:** ten planning documents. No application, script, migration, environment or test exists. Every command named anywhere is **proposed**; do not report one as run.

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
- No AI function. No file storage. No cache. Adding any of these needs a new AD and a review of R-05, R-13, R-14 and R-16.
- No build task before T-0.4.3 records "go".

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
