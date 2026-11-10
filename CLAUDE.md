# CLAUDE.md — ClaimCheck Rehab

Read [AGENTS.md](AGENTS.md) first; it is canonical. This file adds what is specific to this product.

## The buyer's workflow in five lines

1. A BC physiotherapy clinic on Jane bills ICBC by re-keying each invoice into ICBC's portal and bills WorkSafeBC through Teleplan from Jane.
2. ICBC wants the invoice within 45 calendar days of the visit; WorkSafeBC within 90, with a correction window after a rejection (PR-01, PR-07, PR-08 in [Decision.md](Decision.md#41-payer-rules-that-cause-non-payment-physiotherapy)).
3. Jane shows invoice states and WorkSafeBC rejections; no Jane page read shows days left to those deadlines.
4. Once a week staff export two Jane reports; the browser removes identifiers; the product returns a dated list.
5. Staff act in Jane or the payer's portal, mark the item, and the next export confirms it.

The buyer is the clinic owner; the pilot is CAD 89 a month for three months after a free 90-day audit ([Decision.md section 7](Decision.md#7-offer-pilot-and-what-the-price-buys)).

## The question every change must serve

What can a BC clinic recover **beyond Jane's existing rejection workflow**? Keep permanent loss, delayed cash and administrative time on separate lines, always. Never add them into one "savings" figure.

## Highest-consequence error

**HCF-1 — a visit that is at risk, or was not checked, is shown as fine.** Second: **HCF-2 — identifiable patient data leaves the clinic or reaches another clinic.**

## Sensitive data

- Clinic rows are pseudonymised personal information of patients, held on behalf of the clinic under BC PIPA. Treat them as personal information.
- Only the 16 fields in [schema.md](schema.md#2-minimum-authorized-pilot-data). Canada only. Use only for that clinic's list and audit.
- The clinic key never reaches the server.

## Prohibited shortcuts

- Do not upload a raw Jane file to the server "temporarily", and do not move the minimiser to the server.
- Do not add a free-text field to an import payload or to an outcome form.
- Do not describe the server guard as proof that no identifier is stored; it reduces the chance.
- In Phase 0, do not accept a clinic file by email, and do not open one that was not prepared with the workbook.
- Do not log or email an invoice reference, claim token, amount or date of service.
- Do not use real clinic rows as fixtures, examples or prompts.
- Do not treat `not_evaluated` as clear, hide it, or let it short-circuit other rules.
- Do not let an unknown claim state, an unmapped code, an out-of-scope discipline or a service date outside the loaded rules read as fine; list and count them.
- Do not treat Jane's "Submitted" mark on an ICBC invoice as proof that ICBC has it.
- Do not write "nothing needs action" without the counts of visits not checked.
- Do not default a missing crash date, injury date, rejection date or fee; do not ask staff to invent one.
- Do not use a payer figure from memory, from the decision brief or from a Jane guide; cite the payer's current document (two Jane guides were out of date on 2026-11-10).
- Do not ship chiropractic or massage therapy rules until their guides are read and cited.
- Do not count "marked done" as recovered; only an export showing payment on a near-limit item counts.
- Do not add permanent loss, delayed cash and minutes into one figure, in a report or in a gate.
- Do not bypass row-level security with a privileged connection in application code.
- Do not start build work before the stop rule is read (T-0.4.3).

## First verification checks when implementation begins

1. UT-16 and E2E-09: an unknown state is listed as "could not check" and nothing says "fine".
2. UT-17: an ICBC invoice marked Submitted in Jane keeps its 45-day limit.
3. IT-17: a planted escape makes M-09 equal 1 and raises an alert.
4. UT-11, UT-12, UT-15 and IT-09: only the 16 fields leave the browser; the server refuses the identifier fixtures and stores nothing.
5. IT-06: a second clinic gets 404 and the database returns zero rows.
6. UT-01, UT-02, UT-03: the three deadline rules on their boundary days.
7. UT-05: one rule `not_evaluated`, the others still answer.
8. IT-08: marked submitted, export disagrees, item reopens.
9. IT-11 and IT-12: deletion, then restore with replay.

Definitions: [execution-plan.md](execution-plan.md#planned-tests). B1 run of 2026-11-11 ([verification-report-fixing.md](verification-report-fixing.md#b1-implementation-record-2026-11-11)): checks 1 to 8 ran and passed, except that E2E-09 ran only as an API-level counterpart (no UI); check 9 (IT-11, IT-12) is `Not run`.
