# Verification, report and fixing — ClaimCheck Rehab

Labels and sources: [Decision.md](Decision.md#how-numbers-are-labelled-used-in-all-ten-files). This file is the single home of the production risk register (R-01 to R-22), the findings register (F-nnn, reserved for the independent reviewer) and the author's self-check log (SC-nn). No application exists; nothing in this repository has been executed as software.

**Highest-consequence failure (same name as in [PRD.md](PRD.md#12-highest-consequence-failure-and-highest-cost-user-mistake) and [CLAUDE.md](CLAUDE.md)):** **HCF-1 — a visit that is at risk, or was not checked, is shown as fine.** Ranked second: **HCF-2 — identifiable patient data leaves the clinic or reaches another clinic.** (The order was reversed in fix round 1, finding F-003.)

## 1. Checks performed on the documents and repository

Performed by the author on 2026-11-10. This is self-checking, not independent review.

| Check | Method | Result |
|---|---|---|
| Ten required files present, nothing else | Directory listing | Done — see SC-01 |
| Internal links and anchors resolve | Script over all Markdown links | Done — SC-02 |
| Every ID referenced is defined (MH, T, S, R, AD, UT, IT, E2E, SRC, PR, M, rule codes) | Script | Done — SC-03 |
| Every MH in the traceability matrix; 22 risk rows with existing task IDs | Script | Done — SC-04 |
| Schema, screens, APIs and tasks agree | Script for names, plus reading | Done — SC-05 |
| Economics re-run | Script recomputing every figure in Decision.md sections 8–12 | Done — SC-06 |
| Primary sources opened | Listed in [Decision.md section 15](Decision.md#15-sources-and-assumptions) | 29 opened and read (SRC-31 added in fix round 1); 1 blocked (SRC-29); 1 title only (SRC-30) |
| Brief compared with sources | Reading | Departures recorded — SC-07 |
| Security and accessibility citations | Requirement and criterion text read before citing | Done — SC-08 |
| No credentials, no real customer data, Mermaid only | Reading and pattern search | Done — SC-09 |

## 2. Application checks planned for future implementation

Every row is **Not run**. Definitions are in [execution-plan.md](execution-plan.md#planned-tests).

| Check | Covers | Status |
|---|---|---|
| UT-01 to UT-08 rule fixtures | MH-03, MH-04, MH-12 | Not run |
| UT-09 determinism | MH-03 | Not run |
| UT-10 near-limit date and class transition | MH-04, MH-08 | Not run |
| UT-11 minimiser; UT-12 and UT-15 guard; IT-18 stored-data scan | MH-01, HCF-2 | Not run |
| UT-16 could-not-check; UT-17 ICBC submitted in Jane; UT-18 support sessions; UT-19 effective dates; IT-16 old-import banner; IT-17 escape count; E2E-09 no false "fine" | MH-03, MH-04, MH-05, HCF-1 | Not run |
| IT-19 exports supplied and no-export email | MH-08, MH-09 | Not run |
| UT-13 job state; UT-14 settings | R-01, R-06 | Not run |
| IT-01 to IT-05 import | MH-01, MH-02 | Not run |
| IT-06 cross-clinic denial; IT-15 operator grant | MH-10, HCF-2 | Not run |
| IT-07, IT-08 outcomes | MH-07 | Not run |
| IT-09 guard rejection | MH-01, HCF-2 | Not run |
| IT-10 interrupted finalize | R-01, R-19 | Not run |
| IT-11 deletion; IT-12 restore replay | MH-11 | Not run |
| IT-13 migrations | R-08 to R-11 | Not run |
| IT-14 weekly email | MH-09, R-16 | Not run |
| E2E-01 to E2E-08 | All screens | Not run |
| Phase 0 dry run of the data procedure (T-0.1.5) | HCF-2 in the hand-run phase | Not run |
| Accessibility manual checks (T-5.2.4) | [design.md](design.md#8-accessibility-map) | Not run |
| Restore drill (T-6.1.1), rollback rehearsal (T-6.1.3), alert tests (T-6.1.2) | Operations | Not run |
| Security review against targeted ASVS 5.0.0 requirements (T-6.1.4) | [TRD.md](TRD.md#security-requirements-targeted) | Not run |
| Phase 0 hand audits (T-0.3.2) and stop rule (T-0.4.3) | The decisive question | Not run |

## 3. Traceability of must-haves

| MH | Screen or API | Design or architecture decision | Schema or permission | Task | Planned test |
|---|---|---|---|---|---|
| MH-01 | S-04, S-05; POST `/imports/{id}/rows` | AD-01, AD-02, DD-05 | 16-field list in schema section 2; `import_row`; guard | T-0.1.5, T-3.1.1, T-3.1.2, T-3.1.4 | UT-11, UT-12, UT-15, IT-09, IT-18 |
| MH-02 | S-05, S-06, S-14; POST `/imports`, `/imports/{id}/finalize` | DD-05 | `export_profile`, `import_batch` counts check | T-1.1.2, T-3.1.1, T-3.1.3, T-3.1.5 | IT-01, IT-03, E2E-04 |
| MH-03 | S-07, S-08; GET `/items`, `/items/{id}` | AD-04, DD-03, DD-04 | `rule_version` (effective range on every rule), `finding` (outcome, reason) | T-4.1.1, T-4.1.2, T-4.1.3 | UT-01–UT-09, UT-16–UT-19 |
| MH-04 | S-07 banner; `evaluate_clinic` job | AD-05 | `evaluation_run`, `item.limit_date` | T-4.1.4 | UT-01, UT-10, IT-16, IT-17 |
| MH-05 | S-07; GET `/items?view=week`, `/items/export.csv` | DD-01, DD-02, DD-04 | `item`; index (`clinic_id`,`status`,`limit_date`) | T-4.2.1 | E2E-01, E2E-02, E2E-09, UT-17 |
| MH-06 | S-09; GET `/items?view=unpaid` | DD-02 | `visit` index (`clinic_id`,`payer`,`submission_state`,`date_of_service`) | T-4.2.3 | E2E-02 |
| MH-07 | S-08; POST `/items/{id}/events`, `/items/bulk-events` | DD-06 | `item.status`, `item_event` (`reason_code`), `visit_snapshot` | T-4.2.2 | IT-07, IT-08, UT-17, E2E-03 |
| MH-08 | S-10; GET `/pilot-report`, POST `/time-logs` | DD-06 | `item.reached_near_limit_on` (written once), `paid_after_flag`, `time_log` | T-5.1.1 | UT-10, IT-08, IT-19 |
| MH-09 | Monday email; S-15 | AD-08 | `email_dispatch` unique per week | T-4.2.4 | IT-14, IT-19, E2E-09 |
| MH-10 | S-01, S-02, S-03, S-11, S-16; `/auth/*`, `/users`, `/invites` | AD-03 | RLS policies; `session`, `totp_credential`; permission table | T-2.2.2, T-2.2.3, T-2.2.4 | IT-06, IT-15, E2E-05 |
| MH-11 | S-12; GET `/data-export.csv`, POST `/deletion-requests` | AD-02 | `deletion_request`; retention table | T-5.1.2, T-5.1.3, T-0.4.4 | IT-11, IT-12, E2E-06 |
| MH-12 | S-13, S-14; `/ops/rule-versions`, `/rule-changes` | AD-04, AD-10 | `rule_version` (effective range, exclusion constraint) | T-1.1.1, T-4.1.5 | UT-07, UT-09 |
| MH-13 | S-06, S-12, S-15 | AD-08 | `audit_event` append-only | T-2.2.5, T-5.1.3 | IT-06, IT-09 |

**Paid-pilot promise walked end to end:** "a Monday list of visits about to pass a payer deadline" → MH-04, MH-05 → S-07 → `owner` or `staff` under RLS → `item` ordered by `limit_date` → daily `evaluate_clinic` with retry → T-4.1.4, T-4.2.1 → UT-01, E2E-01. Before the application: T-0.4.2.

**HCF-1 walked end to end (a false "fine"):** MH-03(b, e), MH-04, MH-05(e, f), MH-07(e) → S-05 review counts, S-07 count line and "could not check" group, S-08 portal-verification outcome, S-10 escape card → any clinic user under RLS → `visit.submission_state = unknown`, `finding.outcome = not_evaluated` with reason, `rule_version` effective range, `item.limit_date` kept on ICBC submitted rows → failure sequence and recovery in [TRD.md](TRD.md#highest-consequence-failure-hcf-1); M-09 and alerts → T-4.1.1, T-4.1.4, T-4.2.1 → UT-16, UT-17, UT-18, UT-19, IT-16, IT-17, E2E-09. Before the application: T-0.3.2 (rows sorted into in scope, could not check, no rules applied; 10% second pass) and T-0.4.2 (weekly escape check).

**HCF-2 walked end to end:** MH-01, MH-10 → S-05 review step → server guard (schema, plausibility) and RLS → `import_batch.status = rejected_guard`, `audit_event`, `identifier_scan` → recovery sequence in [TRD.md](TRD.md#second-ranked-failure-hcf-2) → T-3.1.2, T-2.2.2 → UT-12, UT-15, IT-09, IT-18, IT-06. Before the application: the [Phase 0 data procedure](execution-plan.md#phase-0-data-procedure), T-0.1.5 (dry run) and T-0.3.1 (step 4 check before a file is kept).

## 4. Findings register

Findings are raised by the independent reviewer (round 1 notes are kept outside this repository). The author records the fix here. The retest column gives the independent reviewer's round 2 verdicts word for word: 11 closed, 1 closed with a part open, 0 still open; at most two fix rounds were allowed and both are used.

| ID | Severity | File and location | Evidence | Impact | Owner | Fix | Retest result |
|---|---|---|---|---|---|---|---|
| F-001 | Blocker | execution-plan Phase 0, T-0.3.1, T-0.4.2; schema 2 and 9; Decision 6 and 12 | Phase 0 handled real patient rows with no by-hand tokenisation, transfer or delivery channel; the outreach text promised controls that did not exist | The first clinic export would breach the repository's own minimum-data definition | Author | Written Phase 0 data procedure (preparation workbook at the clinic, sequential claim codes, encrypted drive or ca-central-1 bucket, never email, step-4 check, delivery by link, mailbox clean-up, retention). New task T-0.1.5 with a dry run; T-0.1.3 and T-0.3.1 acceptance checks test it; outreach gated on both; messages and objections reworded to match. Still open by nature: counsel's reading (O-5) | Closed — independent reviewer, 2026-11-10, note `_coordination/review/claimcheck-rehab-round2.md` |
| F-002 | Major | PRD 11; Decision 7, 11.3, 13; PRD 13 | "Stale" was true of every flagged item, so M-01 and the refund test could not fail; the amount gate added classes and compared a balance with a monthly figure; three build gates; M-02 could not see WorkSafeBC; test power shown only at 5% | The decisive question was not measured | Author | "Stale" replaced by "near-limit" (within 14 days of a payer limit or past it), which is zero for a clinic that invoices on time; each class has its own evidence rule (M-01 to M-04); amount gate uses two separate medians with stated conversions (÷ 1.5 for permanent loss; near-limit delayed cash ÷ 0.5 per 15-day band, corrected from ÷ 3 after the retest); one build gate (Decision 11.3), the other two tables reworded; M-02 states it cannot measure WorkSafeBC as a rate; power shown at 10%, 12.5% and 15% with a "weak pass" rule. Still open: M-01 remains an upper bound on what the product caused (O-10) | Closed, part open: near-limit delayed cash is divided by 3 although collectable ICBC near-limit items span only a 15-day service band, understating the monthly figure about sixfold — independent reviewer, 2026-11-10, note `_coordination/review/claimcheck-rehab-round2.md`. Residue edited after retest; checked by the lead, not re-reviewed |
| F-003 | Major | PRD 12; CLAUDE.md; TRD rules and runtime view; schema; this file section 3 | A false "fine" was ranked second with no sequence or tests; `unknown` state, ICBC invoices marked Submitted in Jane, and support sessions could read as clear | A visit passes a deadline while shown as fine | Author | Ranked first as HCF-1 in PRD, CLAUDE.md, TRD and here; data exposure is HCF-2. Scope check before rules; "could not check" and "no rules applied" listed and counted, never `clear`; ICBC-07 keeps the 45-day limit and asks for portal verification; WSBC-04 and WSBC-07 count 19107 and 19108; failure sequence, recovery and tests UT-16 to UT-19, IT-16, IT-17, E2E-09 added; M-09 computed at each evaluation | Closed — independent reviewer, 2026-11-10, note `_coordination/review/claimcheck-rehab-round2.md` |
| F-004 | Major | Decision 4.1; TRD rules; execution-plan UT-07 | Hand Therapy fees from 2026-09-27 missing; effective dates only on fees; codes missing from PR-11; ICBC-04 and ICBC-05 over-certain; date discrepancy on the WorkSafeBC manual | False flags and false clears on older invoices | Author | PR-05 carries 97 / 110 / 145 from 2026-09-27; an effective-date table covers every rule, with "could not check" outside it; PR-11 lists 19106–19109, 19171, 19193, 19313 and treats any other code as unmapped; ICBC-04 and ICBC-05 are "check with ICBC", no amount; the date discrepancy is recorded; SRC-31 opened. Still open: payer documents before 2026-04-01 not read (O-11) | Closed — independent reviewer, 2026-11-10, note `_coordination/review/claimcheck-rehab-round2.md` |
| F-005 | Major | TRD import handling, threat model; schema `item_event`; UT-12 | The guard was described as making identifiers impossible; `invoice_ref` accepted a health number or a surname; free-text reason; nothing scanned stored data; operator's infrastructure access unstated | The last control before HCF-2 was weaker than claimed | Author | Claim withdrawn and restated as risk reduction; plausibility checks (health-number check digit, letters-only, distinct-share, date ranges), profile-specific invoice format, closed code list, reason list in place of free text, daily `identifier_scan`; fixtures UT-15 and IT-18, including one that passes and is recorded as the residual gap; founder's infrastructure access stated as a trust limit. Still open: residual gap (O-12); invoice-number format (O-2) | Closed — independent reviewer, 2026-11-10, note `_coordination/review/claimcheck-rehab-round2.md` |
| F-006 | Major | Decision 1, 9.3, 9.6, 12 | Cap of 3,500 against 5,220 spent by day 90 on the document's own ramp | The amount to approve was not the amount spent | Author | One Phase 0 figure: planned 5,220 (1,620 + 2,100 + 1,500), cap 5,500, used in Decision 1, 9.3 and 12, PRD 10 and execution-plan 0.1; the 30/60/90 table includes fixed cost; "month 7" corrected | Closed — independent reviewer, 2026-11-10, note `_coordination/review/claimcheck-rehab-round2.md` |
| F-007 | Major | Decision 4.2, 4.4, 12; TRD ICBC-06 | Under-billing loss unsupported; Jane's date filter omitted | The increment over Jane was overstated | Author | Under-billing claim withdrawn in Decision 4.2; G-5 and ICBC-06 reclassed to "Jane set-up" with a loss only where a paid amount is below the schedule; date filter added to 4.2, G-1, G-2, the outreach message and objection 1; the increment restated as a computed deadline per invoice across payers without a manual filter | Closed — independent reviewer, 2026-11-10, note `_coordination/review/claimcheck-rehab-round2.md` |
| F-008 | Minor | design S-05; UT-11 | 25 columns against a 22-column fixture | Inconsistent example | Author | S-05 shows 14 kept + 2 coded + 6 removed = 22 | Closed — independent reviewer, 2026-11-10, note `_coordination/review/claimcheck-rehab-round2.md` |
| F-009 | Minor | Decision 12 | Referral offer, LinkedIn script, first-3 case study and the 600 budget dropped without note | Brief content lost | Author | Recorded in Decision 12 and 9.3; case study added to T-0.3.3 | Closed — independent reviewer, 2026-11-10, note `_coordination/review/claimcheck-rehab-round2.md` |
| F-010 | Minor | TRD identity; exports | No lost-second-factor flow; no formula-injection note | Recovery route undefined | Author | Lost-factor flow added and listed against ASVS 6.4.4 (unverified); CSV cells neutralised; free-text reason removed; 8.4.2 recorded as not met | Closed — independent reviewer, 2026-11-10, note `_coordination/review/claimcheck-rehab-round2.md` |
| F-011 | Minor | execution-plan 0.1, 0.4 | "Owner" meant both clinic owner and project owner | Ambiguity | Author | "Portfolio owner" and "clinic owner" used in those places | Closed — independent reviewer, 2026-11-10, note `_coordination/review/claimcheck-rehab-round2.md` |
| F-012 | Minor | SC-10 | Word count stated as 28,000; reviewer counted 31,300 | Wrong figure | Author | SC-10 restated with the counting method and the count after fix round 1 | Closed — independent reviewer, 2026-11-10, note `_coordination/review/claimcheck-rehab-round2.md` |

### Outstanding items

Open after two fix rounds; none can be closed by editing documents.

| # | Item | Needed to close | Task |
|---|---|---|---|
| O-1 | No customer has been interviewed; willingness to pay unproven | 16 audits and payments | T-0.3.2, T-0.4.3 |
| O-2 | Exact Jane export headers; whether state dates, crash date, injury date and claim number are exported; the format of Jane invoice numbers (needed by the identifier guard) | Header-only files from a clinic | T-0.1.2 |
| O-3 | Whether Jane shows a deadline clock in the live product | Live-account check | T-0.1.2 |
| O-4 | Reachable pool not counted; 600 is an assumption | Counted list | T-0.1.4 |
| O-5 | Legal reading of PIPA s. 18(2) and s. 35, ICBC terms, WorkSafeBC agreement, college standard | Counsel's note | T-0.1.3 |
| O-6 | TELUS eClaims page blocked; chiropractic and massage guides not read | Access; reading | T-1.1.1 |
| O-7 | ASVS 14.3.3 not met by design (clinic key in browser storage) | Decision to accept or redesign | T-1.1.4 |
| O-8 | Build estimate 356–574 hours against the chat's 120 | Portfolio owner's decision on scope | T-0.4.3 |
| O-9 | Economics do not reach break-even with founder pay on the chat's inputs | Evidence in [Decision.md section 13](Decision.md#13-what-buyer-evidence-would-change-the-decision) | T-0.4.3 |
| O-10 | M-01 is an upper bound: a payment on a near-limit item is not proof the product caused it (F-002) | Jane state dates from T-0.1.2, to compare each clinic's own lag before and during the pilot | T-0.1.2, T-6.2.3 |
| O-11 | Payer documents in force before 2026-04-01 not read; older invoices are "could not check" (F-004) | The earlier ICBC guide and WorkSafeBC agreement | T-1.1.1 |
| O-12 | The identifier guard can pass a patient-number column with few repeats or a child's birth date; the founder holds infrastructure credentials (F-005) | Jane invoice-number format; a second person or an external audit log review | T-0.1.2, T-1.1.4 |
| O-13 | The Phase 0 procedure depends on clinic staff following a workbook; it is not enforced by software (F-001) | Dry run, then observed first preparation at each clinic | T-0.1.5, T-0.3.1 |
| O-14 | The payment test is weak between 10% and 15% close rates (F-002) | More audits, or acceptance of the "weak pass" rule by the portfolio owner | T-0.4.3 |
| O-15 | Whether the 12-hour session limit and the 5-minute code step meet WCAG 2.2.1 | Manual check | T-5.2.4 |
| O-16 | F-002 residue: the near-limit conversion was changed from ÷ 3 to ÷ 0.5 per 15-day band after the reviewer's retest; checked by the lead, not independently re-reviewed. The steady-flow and 30-day-month assumptions behind it are untested | An independent re-check; real band balances from the audits | T-0.3.2, T-0.4.3 |

### Author self-check log (not independent review)

| ID | Check | Result |
|---|---|---|
| SC-01 | File inventory | Exactly the ten required files |
| SC-02 | Links and anchors | All relative links and in-file anchors resolve |
| SC-03 | ID definitions | Every MH, T, S, R, AD, DD, UT, IT, E2E, SRC, PR, M, G and rule code that is referenced is defined once |
| SC-04 | Matrix and register | 13 of 13 MH rows; 22 of 22 risk rows; every task ID in them exists in execution-plan.md (62 tasks after fix round 1) |
| SC-05 | Cross-file agreement | 16 screens in App-flow and referenced; 24 tables in the dictionary, each in the diagram; every API in the matrix is in the TRD table; phase hour totals equal the sum of task ranges |
| SC-06 | Arithmetic | Gross profit, payback, lifetime value, both break-evens, tier mix, pilot economics, both ramp tables, unlimited-pool figures, funnel, 30/60/90 table and all binomial probabilities recomputed by script and equal to the text |
| SC-07 | Brief versus sources | Four departures recorded in Decision.md: the "rejected or pro-rated" wording (4.1); Jane guide figures out of date against the payers (4.2); ICBC's own tool added as an alternative (5); TELUS unverified (5). The brief's two "secondary" items: SRC-14 now opened; SRC-30 still title only |
| SC-08 | Standards | Each ASVS 5.0.0 requirement and WCAG 2.2 criterion cited was read in the source; gaps are written as "not met", not beside a compliance claim |
| SC-10 | Length | Counted with `wc -w`, which also counts table bars and symbols: about 31,300 before fix round 1 and about 38,700 after it, against the 16,000–20,000 target. Not cut: the additions are the Phase 0 procedure, the failure sequence, effective dates and tests that the findings required |
| SC-11 | Fix round 1 | All 12 findings addressed and recorded above; link, ID, hour-total and arithmetic checks re-run after the edits; new figures (5,220 and 5,500; 51.5%, 38.8%, 28.4%; 600, 57.445, 13 and 117; Phase 0 hours 169–293) recomputed by script |
| SC-12 | After retest | Reviewer verdicts recorded for F-001 to F-012; F-002 residue corrected in Decision.md 11.3 (bands of 15 days, 0.5 month; 291 → 582; threshold 150 = balance 75; one visit = 194; early stop 50 = balance 25) and cited in PRD M-01, execution-plan T-0.3.3 and T-0.4.3; link, ID, hour-total and arithmetic checks re-run |
| SC-09 | Hygiene | No credential, token, real clinic or real patient; names "Harbourview Physio", "Seawall Rehab", "Priya", "Sam" are invented; all diagrams Mermaid; all commands labelled proposed |

## Production risk register

Numbering as in the assignment specification, section 7. "Signal" is what would reveal the risk in operation. Every test is **Not run**.

| ID | Impact for this product | Prevention | Detection signal | Test and expected outcome | Task |
|---|---|---|---|---|---|
| R-01 Out-of-order or duplicate events overwrite a newer job state | An older Jane export, or a late job completion, makes a submitted ICBC invoice look unsubmitted again, or a failed import look complete; staff chase the wrong visits | Lease-token guard on job completion; a snapshot older than `visit.last_export_date` never overwrites current state | Log line "completion ignored: stale lease"; count of older-export imports | UT-13: zero rows updated. IT-05: current state stays from the newer export | T-2.2.6 |
| R-02 A caller timeout prevents reconciliation with a valid later completion | Staff's browser times out during a large import, they upload again or believe it failed, while the first import finishes | API returns 202; status polled; same content hash returns the same batch | Batches `completed` with no status read by the client | E2E-08: refresh during processing shows the same batch; double Confirm creates one | T-3.1.3 |
| R-03 New utilities duplicate behaviour already owned by shared code | A second date-difference helper counts the 45 days differently from the rule engine; list and item detail disagree by a day | All date, money and tenancy helpers live in `packages/core`; lint bans `date` arithmetic elsewhere | Lint failure; review checklist | Lint rule test: a helper added in `apps/api` fails CI | T-2.1.1 |
| R-04 Applications import private code across architectural boundaries | The web app imports rule internals and ships payer parameters or guard logic it should not own; the worker breaks when the API changes | Import-boundary lint; `packages/core` public interface only | Lint failure | A cross-app import fails CI | T-2.1.1 |
| R-05 Tenant enforcement is scattered or bypassed through APIs, workers, caches or files | One clinic sees another clinic's patient billing rows: HCF-2 | Row-level security in the database; one tenancy module; worker sets the clinic per job; no cache, no files; CI lists tables without a policy | `cross_clinic_denied` audit events; RLS audit script output | IT-06: 404, audit event, zero rows under the wrong setting, worker confined | T-2.2.2 |
| R-06 Workers copy configuration and utility modules, causing behavioural drift | The worker evaluates with a different timezone or fee table from the API; Monday's email count differs from the list | One settings module and one rule package imported by both | Email count differs from list count (compared in the weekly job) | UT-14 for settings; IT-14 compares counts | T-2.1.1 |
| R-07 Worker logging imports web-only modules and crashes during startup | The daily evaluation never runs; days-left figures go stale without anyone noticing | `packages/core.logging` has no web import; worker image built without the web framework | Worker heartbeat missing; "last evaluated" banner | Worker starts in an image without FastAPI installed | T-2.1.5 |
| R-08 ORM declarations omit indexes or constraints present in migrations | The unique key on (`clinic_id`,`invoice_ref`,`line_no`) is missing in a fresh database and duplicate visits double the amounts | Parity check in CI | CI failure | IT-13: parity passes; removing an index from the model fails | T-2.2.1 |
| R-09 Interrupted migrations or backfills cannot resume safely | A backfill of `first_rejected_on` stops half-way; WSBC-02 limits are wrong for half the clinics | Backfills separate from migrations, batched, checkpointed, idempotent | Checkpoint row not at "done" | IT-13: interrupted backfill resumes and finishes with the same result | T-2.2.1 |
| R-10 Merged branches introduce conflicting migration order | Deploy fails on Monday morning before the email job | Single-head check in CI; timestamped names | CI failure | IT-13: second head fails the build | T-2.1.3 |
| R-11 Index creation locks busy production tables during deployment | Imports and lists hang for every clinic during a deploy | `CREATE INDEX CONCURRENTLY`; lock and statement timeouts; deploy outside Monday 07:00–11:00 Pacific | Lock-wait alerts; invalid index in the status report | IT-13: a failed concurrent index is detected and rebuilt | T-2.2.1 |
| R-12 Correlation IDs disappear across jobs and retries, or sensitive data leaks into logs | A failed import cannot be traced for a clinic; or invoice references and amounts sit in log storage outside the retention rules | ID stored on batch, job and audit event and passed to retries; log fields restricted to IDs and counts | Log scan matches; job log line without an ID | Proposed `scripts/log_scan.py` returns no match after E2E-01; a retried job logs the original ID | T-2.1.5 |
| R-13 Upload keys collide or fail to isolate tenant, source and purpose | **Not applicable to files:** no file is uploaded or stored (AD-02). The equivalent identity is `import_batch` unique on (`clinic_id`,`content_hash`) and `import_row` on (`batch_id`,`kind`,`row_no`), all under RLS. It would apply fully if remittance documents or raw exports were ever stored | Keep AD-02; if files are added, keys must begin with clinic, source and purpose | Any object-store dependency appearing in the build | IT-02: same content, same clinic → same batch; same content in the second clinic → separate batch | T-3.1.2 |
| R-14 Temporary uploads survive retention expiry or failed cleanup | Staging rows of a failed or abandoned import (pseudonymised billing data) stay beyond 24 hours | `retention_purge` daily; purge on batch completion; audit-only clinics purged at 30 days | Count of `import_row` older than 24 hours on the operator view | After IT-03 and a simulated day, no `import_row` remains for the batch | T-5.1.2 |
| R-15 Missing persistent volumes cause data loss after service recreation | Recreating the containers loses every clinic's history and the pilot measurement | Containers hold no state; data only in RDS with 35-day backups; local database on a named volume | Readiness fails on an empty schema | T-6.1.1 drill; containers recreated on staging with no data change | T-2.1.4 |
| R-16 Generated file links use internal hosts or `localhost` behind a public proxy | The Monday email links to an address staff cannot open; nobody sees the list | Links built only from `PUBLIC_BASE_URL`; start-up refuses a non-HTTPS or local value in production | Click-through rate of zero; start-up error | IT-14: link host equals the configured public host | T-4.2.4 |
| R-17 Local dependencies and workers lack a reliable single startup command and health checks | A new developer runs the API without the worker; evaluations never run locally and a rule bug ships | `make dev` (proposed) starts all services with health checks | Health summary shows a missing service | Fresh clone to healthy in one command | T-2.1.2 |
| R-18 Browser Back, refresh or deep links lose the user's result or task state | Front-desk staff, interrupted by a patient, lose their place in the list or an import review | List state in the URL; import resumable; outcomes idempotent | Support messages; repeated imports | E2E-02, E2E-08 | T-4.2.1 |
| R-19 Bulk processing skips files, hides partial failures or duplicates successful work on retry | Rows silently missing from an import mean visits never checked: HCF-1 | Counts must add up (database check); rejected rows listed; idempotent upserts; bulk outcomes report each item | `completed_with_rejects` rate; count mismatch refused by the constraint | IT-03, IT-10, E2E-03 | T-3.1.3 |
| R-20 Unclear labels, icons, stale routes or broken links misdirect users | "Lost" read as "nothing to do" when it is discretionary and worth submitting; staff skip recoverable money | Fixed class names with words and icons; discretionary and certain kept apart; route table tested | "Not an error" reasons mentioning confusion; 404s on internal links | E2E-07; link check across routes | T-4.2.1 |
| R-21 Unrequested features consume effort without a requirement or pilot need | Building remittance reading or chiropractic rules before any clinic pays | Every merged change cites an MH or R; non-goals list | Changes without a reference | Release checklist review | T-6.1.5 |
| R-22 Misnamed, duplicate or stale branches obscure the active work or endanger unmerged changes | A rule fix for a payer change sits on a forgotten branch while clinics are checked against the old fee | Branch naming `type/T-x.y.z-slug`; delete on merge; weekly list of branches older than 14 days | Branch list | Checklist shows no merged branch remaining | T-6.1.5 |
