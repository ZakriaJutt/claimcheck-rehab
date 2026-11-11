# Decision — ClaimCheck Rehab

**Question this file answers:** can a BC physiotherapy clinic owner justify paying for ClaimCheck Rehab, and should the founder spend money finding out?

**Decisive pilot question for the whole repository:** what can a BC clinic recover beyond Jane's existing rejection workflow? Permanent losses, amounts past a payer deadline (payment at the payer's discretion, not a confirmed loss), delayed cash and administrative time are measured separately, on the minimum authorized pilot data.

Status: planning document. Nobody has interviewed a customer. Willingness to pay is unproven.

## How numbers are labelled (used in all ten files)

| Tag | Meaning |
|---|---|
| `[C]` | Stated in the chat (the earlier discussion, received through the decision brief). A price, an offer or a research note, not evidence. Every unit-economics input and funnel rate carried from the chat is an **assumption** and is written `[C, assumption]`. |
| `[S: SRC-nn]` | Read by the author on 2026-11-10 at the source listed in [section 15](#15-sources-and-assumptions). |
| `[A]` | Assumption made by the author. Not decided in chat. |
| `[P]` | Proposal by the author. Not decided in chat. |
| `[D]` | Derived by arithmetic from tagged inputs shown beside it. |

"Not decided in chat" means the earlier discussion left the point open. Engineering parameters in the other nine files (timeouts, sizes, retention days, hour estimates) are author proposals; each file says so once at the top.

## 1. Proposed decision

**`[P]` Fund Phase 0 only (validation by hand, [execution-plan.md](execution-plan.md)), with a cash cap of CAD 5,500 ([section 9.3](#93-costs-kept-apart)), and do not build the application until the stop rule in [section 11](#11-stop-rule) has been evaluated.** The chat's research verdict was "test", evidence confidence medium `[C]`. This proposal keeps "test" and adds four reasons for the gate:

1. **Jane and the payers already cover more than the chat assumed.** Jane fetches WorkSafeBC remittances every morning and files rejected invoices in a Rejected folder `[S: SRC-03]`; Jane warns when a policy's treatment maximum is reached if staff enter it `[S: SRC-06]`; ICBC's own invoicing tool refuses an invoice beyond the approved count or end date `[S: SRC-15]` and shows a 45-day alert `[S: SRC-14]`. The gap that remains is narrower ([section 4](#4-what-jane-and-the-payers-already-do-and-what-remains)).
2. **The gap that remains is time-based.** ICBC and WorkSafeBC both set deadlines counted from the date of service `[S: SRC-12]` `[S: SRC-19]`. No Jane page opened describes a countdown against them. Whether clinics actually miss them is unknown and can be measured by hand on one export.
3. **The economics do not close on the chat's own inputs.** At 250 clinics contacted a month the account base converges to about 64, below the 99 needed with founder pay `[D]` ([section 9.6](#96-cash-during-the-acquisition-ramp)).
4. **The data is patient information.** A clinic can lawfully hand billing rows to a contractor working for it `[S: SRC-25]`, but only for its own billing purpose. That shapes what the founder may keep ([section 6](#6-minimum-authorized-pilot-data)).

## 2. Who pays, who uses, what is billed

| Term | Definition |
|---|---|
| **One paying account** `[P]` | One clinic **location** (one Jane account location, one ICBC vendor number or WorkSafeBC payee number set) with at least one paid monthly invoice. A two-location owner is two accounts. Not decided in chat. |
| **One billable unit** `[P]` | One location-month. No per-visit or per-practitioner fee `[C]` ("usage: None"). |
| Buyer and budget owner | Clinic owner `[C]`. |
| Daily user | Front-desk or billing staff who key claims and reconcile payments `[C]`; clinic manager where one exists. |
| Signs the pilot and data agreement | Clinic owner, as the person responsible for the clinic's compliance with PIPA `[S: SRC-25]` s. 4. |
| Supplies data | Front-desk staff, weekly, from Jane. |
| Can block | The owner's privacy concern; a bookkeeper or billing contractor who already does the reconciliation. |

## 3. Launch market, problem, workaround

- **Launch market `[C]`:** physiotherapy clinics in Metro Vancouver with ICBC and WorkSafeBC caseloads, using Jane. Ideal profile `[C]`: 4–25 practitioners, 5–40 staff, at least 20% of visits billed to ICBC or WorkSafeBC.
- **Problem `[C]`:** "wrong fee codes, missing claim numbers, late invoices and sessions past approved limits lead to rejections and unpaid visits. Front-desk staff find out weeks later, if at all." Frequency: daily; every insured visit is a claim.
- **Workaround `[C]`:** staff key claims into Jane, Teleplan, ICBC's portal and insurer portals, reconcile by hand; many clinics run a monthly unpaid-claims spreadsheet.
- **Why now `[C]`:** ICBC program guide changes, a year-end review that shows unpaid ICBC visits, front-desk turnover. Supporting fact: ICBC's physiotherapy guide and fee schedule changed on 2026-04-01 and again on 2026-09-27 `[S: SRC-12]` `[S: SRC-13]`; WorkSafeBC's manual page is dated June 2026 and the manual is read with the Physiotherapy Services Memorandum of Agreement and schedules effective 2026-04-01; its fee schedule is dated 2026-03-23 `[S: SRC-19]` `[S: SRC-20]`.

## 4. What Jane and the payers already do, and what remains

### 4.1 Payer rules that cause non-payment (physiotherapy)

| ID | Payer | Rule (source wording paraphrased; numbers exact) | Source |
|---|---|---|---|
| PR-01 | ICBC | The firm must submit invoices within 45 calendar days from the date of service; "At ICBC's sole discretion, invoices submitted outside of the 45-day timeframe may not be paid." Passing the 45 days is therefore **not a confirmed loss**: payment is at ICBC's discretion until ICBC's own outcome is known (C1, 2026-11-11). | `[S: SRC-12]` §6.1 |
| PR-02 | ICBC | 25 standard sessions, including the Initial Visit, are pre-authorized in the Early Access Period, defined as the first 12 weeks (84 days) after the crash. | `[S: SRC-12]` §1, §4.3 |
| PR-03 | ICBC | Services outside the approval period are not eligible for direct billing; payment is not made or backdated; a new treatment plan must be approved first. Plans should go in 1–2 weeks before expiry; ICBC answers within five business days. | `[S: SRC-12]` §5; `[S: SRC-18]` |
| PR-04 | ICBC | Initial Visit billed once per customer "unless otherwise approved by ICBC"; no standard treatment charged on the Initial Visit date; no funding for multiple sessions by the same practitioner type on one day. A standard and a non-standard session on one day are possible only if one is invoiced manually after checking with the claims contact. | `[S: SRC-12]` §4.2, §4.3, §4.12 |
| PR-05 | ICBC | Fees for service dates from 2026-04-01: Initial Visit CAD 154; Standard Treatment CAD 97; specialized or extended session CAD 145 (rural or remote, complex musculoskeletal, concussion or vestibular, spinal cord injury, in-home or in-community). From 2026-09-27 only: Hand Therapy specialized session CAD 97 (15 minutes), CAD 110 (30 minutes), CAD 145 (45 minutes); not available before that date. | `[S: SRC-12]` §6.2.1; `[S: SRC-13]` |
| PR-06 | ICBC | A customer cannot be billed for unpaid fees that result from the clinic's breach of the agreement. | `[S: SRC-12]` §6 |
| PR-07 | WorkSafeBC | Invoices must be received within 90 days of the date of service. | `[S: SRC-19]` p. 27 |
| PR-08 | WorkSafeBC | After a rejection the clinic has until the later of 180 days from the date of service or 90 days from the first rejection to correct it; after that the invoice "cannot be paid". MSP pre-edit refusals do not count as a submission. The window does not depend on how old the visit is: a rejected invoice more than 90 (or 180) days after service can still be correctable. | `[S: SRC-19]` p. 27, p. 30 |
| PR-09 | WorkSafeBC | One visit per day per claim. Treatment period: up to 10 visits or five calendar weeks, whichever is earlier. Extension: 8 visits or 4 weeks (16 visits or 8 weeks for five listed injury types), approved before it starts. Support sessions by a kinesiologist or physical-therapist support worker count toward the visits and the one-per-day limit. | `[S: SRC-19]` p. 38 |
| PR-10 | WorkSafeBC | Initial assessment (19100) payable only when the date of service is within 60 days of the date of injury unless an officer approves. 19102 cannot be invoiced with 19100 or 19101. | `[S: SRC-20]` |
| PR-11 | WorkSafeBC | Fees for dates of service 2026-04-01 to 2027-03-31: 19100 CAD 196; 19101 CAD 196; 19102 CAD 95; 19103 CAD 57; 19303 CAD 57; 19105 CAD 45; 19204 CAD 33.25; 19106 CAD 95; 19107 (stand-alone kinesiologist session) CAD 70; 19108 (stand-alone support-worker session) CAD 65; 19109 (complex fee) CAD 115; 19171 (photocopies) CAD 42; 19193 and 19313 (hydrotherapy) CAD 67 and CAD 48 a visit. 19107 and 19108 are not billable on the same day as 19102. Any other code is unmapped and is reported as not checked. | `[S: SRC-20]` |
| PR-12 | WorkSafeBC | Date of service, payee number and fee item must match exactly or the Teleplan invoice is rejected; the claim number must be present. | `[S: SRC-19]` p. 28–29 |

**Effective dates of every rule, not only fees.** A rule is applied only to service dates inside the period for which its source was read; outside it the result is "could not check" (`not_evaluated`), never "fine".

| Rules | Applied to service dates | Basis | Outside that period |
|---|---|---|---|
| PR-01 to PR-04, PR-06 | From 2026-04-01; no end date loaded | The guide read is the 2026-09-27 edition. ICBC's change overviews for 2026-04-01 and 2026-09-27 show no amendment to the 45-day sentence or to sections 4.1–4.3 and 5 `[S: SRC-31]` `[S: SRC-17]`. The start date is an inference `[A]`; the earlier editions were not read. The 45-day alert was shown in HCPIR from 2025-06-15 `[S: SRC-14]` | Could not check |
| PR-05 | Base fees from 2026-04-01; Hand Therapy rows from 2026-09-27 | Columns of `[S: SRC-13]` | Could not check |
| PR-07 to PR-10, PR-12 | From 2026-04-01 `[A]` | C1 (2026-11-11): the manual's page is dated **June 2026** and says the manual is used with the Physiotherapy Services Memorandum of Agreement and "all the related Schedules, which were effective April 1, 2026" `[S: SRC-19]`. The PDF behind the page was created 2026-06-26; its footer still reads "February 2026". PR-07, PR-08, PR-09 and PR-12 read the same on the same pages (27, 29–30, 38–39); the fee codes the manual names (19107, 19108, 19204) match PR-11. Rule versions citing SRC-19 are now version 2 ([TRD.md](TRD.md#deterministic-rules)). The Agreement itself was not opened. Jane's "15 visits or six weeks" may be the earlier rule; that was not checked | Could not check |
| PR-11 | 2026-04-01 to 2027-03-31 | Column of `[S: SRC-20]` | Could not check until the next schedule is loaded |

Audits run between December 2026 and February 2027, so the 90-day window lies wholly after 2026-04-01. **The audit is not limited to that window** (C1): it also covers every older invoice still open, and in particular every WorkSafeBC rejection whose PR-08 correction window may still be open, whatever its service date ([section 6](#6-minimum-authorized-pilot-data), [PRD.md](PRD.md#11-success-metrics) "Look-back set"). Older open invoices with service dates before 2026-04-01 are listed as "could not check: older than the rules loaded" and are counted in no total.

Two departures from the brief, recorded: (a) the brief said an ICBC physiotherapy invoice may be rejected or pro-rated if a *standard* session misses 20 minutes; in the guide read, the "rejected or pro-rated" sentence is attached to *specialized or extended* sessions, and the 20-minute minimum is a definition of the standard treatment `[S: SRC-12]` §6.2.1. (b) Session length is in the clinical record, not in a billing export; the product does not check it ([PRD.md](PRD.md) non-goals).

### 4.2 What Jane already provides

| Capability | Jane (Insurance Billing add-on) | Source |
|---|---|---|
| WorkSafeBC submission | Electronic through Teleplan for physiotherapy and chiropractic | `[S: SRC-02]` `[S: SRC-07]` |
| WorkSafeBC rejections | Remittances fetched every morning; rejected invoices moved to Billing > Rejected; staff correct and resubmit; a guide explains codes | `[S: SRC-03]` `[S: SRC-04]` |
| WorkSafeBC late claims | A Late Submission Reason field for claims over 90 days old | `[S: SRC-05]` |
| ICBC submission | None. Staff open ICBC's portal from Jane, re-key the invoice, then mark it Submitted in Jane | `[S: SRC-06]` |
| ICBC payment | Staff record it by hand once ICBC confirms payment | `[S: SRC-06]` |
| Visit limits | Staff can enter a Maximum Number of Treatments (Jane suggests 25 for ICBC physiotherapy) and an end date; Jane alerts when the maximum is reached | `[S: SRC-06]` `[S: SRC-08]` |
| Unpaid view | Accounts Receivable report by insurer with amounts owing over time; Billing folders by state | `[S: SRC-10]` `[S: SRC-02]` |
| Date filter | Billing lists, including Rejected, can be narrowed by date range, insurer and staff member; with this and the A/R report staff can already list invoices older than a chosen number of days, one payer and one folder at a time | `[S: SRC-03]` `[S: SRC-10]` |
| Exports | Most reports export to Excel; the Insurance Policies report exports to Excel or CSV | `[S: SRC-11]` `[S: SRC-08]` |

**Not described on any Jane page opened** (absence from documentation is not proof of absence in the product; task T-0.1.2 checks a live account): a deadline computed per invoice for the ICBC 45-day or WorkSafeBC 90-day limit; tracking of the WorkSafeBC correction window (PR-08); a check of billing-code amounts against the current payer fee schedule; any ICBC rejection or payment-status feed. The honest size of the increment is therefore: **a computed deadline for every invoice, across both payers, without a manual filter, and a prompt to verify in ICBC's portal the invoices Jane shows as submitted.**

Two of Jane's own guides were out of date on the day they were read: the ICBC physiotherapy guide lists CAD 151 and CAD 95 (and "$93" in one sentence) against ICBC's CAD 154 and CAD 97 `[S: SRC-06]` `[S: SRC-13]`; the WorkSafeBC guide describes a treatment period of "up to 15 visits or six calendar weeks" against WorkSafeBC's 10 visits or five weeks `[S: SRC-07]` `[S: SRC-19]`. The same Jane guide tells readers that ICBC's fee guide is the authority. This shows that a clinic's Jane billing codes can be out of date. **It does not show under-payment, and none is claimed:** ICBC invoices are keyed in HCPIR by service type, and fees below the limit go through a manual process `[S: SRC-12]` §6.1, so Jane's price list does not set what ICBC pays. An earlier draft of this file claimed a CAD 2–3 loss per visit; that claim is withdrawn (finding F-007).

### 4.3 What the payers' own tools already provide

| Tool | What it does | Source |
|---|---|---|
| ICBC HCPIR and Health Care Provider Portal (HCPP) | Refuses an invoice beyond the approved end date or count without a new treatment plan; shows "may not be paid" when invoicing more than 45 days after service; HCPP shows invoice and payment status; the inquiry unit confirms remaining approved treatments | `[S: SRC-15]` `[S: SRC-14]` |
| WorkSafeBC My Provider Services | "Real-time validation will identify errors" before submission; tracks invoices, payment status and extension requests | `[S: SRC-22]` `[S: SRC-24]` |

These checks happen **when staff sit down to invoice**. They do not help if nobody sits down in time, and they arrive after the visit has been delivered.

### 4.4 What remains for ClaimCheck Rehab

| Gap | Why Jane's workflow leaves it | Money class |
|---|---|---|
| G-1 Visits ageing toward the ICBC 45-day or WorkSafeBC 90-day deadline while still unsubmitted | Jane lists them in an Unsubmitted folder that staff can filter by date; no documented per-invoice deadline; ICBC warns only at entry | Delayed cash, turning into *past payer deadline – payment at payer's discretion* (not a confirmed loss) |
| G-2 WorkSafeBC rejected invoices ageing toward the correction limit (PR-08) | Jane's Rejected folder can be filtered by date; the limit depends on two dates and is not computed | Delayed cash, turning into permanent loss only after the latest possible PR-08 limit (the manual: "cannot be paid") |
| G-3 ICBC visits delivered or booked past the approval period or count | Jane alerts only if staff entered the maximum and end date; ICBC blocks only at invoicing, after the visit | Permanent loss |
| G-4 ICBC invoices marked Submitted in Jane that ICBC never received, or with no payment recorded after 30 days `[P]` | Jane has no ICBC status feed; "Submitted" is a manual mark and payment is recorded by hand | Delayed cash, turning into *past payer deadline – payment at ICBC's discretion* after day 45 if the invoice was never keyed or was keyed late |
| G-5 Jane billing-code amounts out of date; billable WorkSafeBC report fees never invoiced (for example 19105) | Jane's billing codes are set by the clinic | Administrative time (a Jane set-up item; no loss is claimed unless a paid amount below the schedule is seen); delayed cash for an unbilled report fee |
| G-6 Time spent building the monthly unpaid spreadsheet | Jane's reports are separate per view | Administrative time |

The classes are defined so that every flagged amount is in exactly one of them on a given day. Forward-looking warnings (a visit booked past an approval) carry no amount and are listed separately. **C1 (2026-11-11):** a payer deadline passed is not a confirmed loss. ICBC's guide says late invoices "may not be paid" at ICBC's sole discretion `[S: SRC-12]` §6.1, so the date alone puts an amount in *past payer deadline*, never in *permanent loss*; only the payer's recorded outcome makes it *confirmed unpaid*. The earlier wording ("already lost", "probably lost", "discretionary permanent loss") is withdrawn.

| Class | Definition `[P]` |
|---|---|
| **Permanent loss** | The payer's own rule text says the amount cannot be paid or is not eligible: PR-08 passed even on the latest possible limit (*certain*: "cannot be paid"), PR-03 service outside approval (*certain*), PR-09 second visit on one day (*certain*), a paid amount below the schedule seen on a paid invoice (*certain*), or written off by the clinic (*realised*). |
| **Past payer deadline – payment at payer's discretion** | PR-01 or PR-07 passed while unsubmitted, or Jane's export dates the "Submitted" mark after the PR-01 limit and no payment is recorded. The payer may still pay. **Not a loss**; reported on its own line, never added to permanent loss. Code: `past_deadline_discretionary`. |
| **Confirmed unpaid (payer outcome recorded)** | Staff saw the payer's outcome (ICBC's portal) refusing payment and recorded it (outcome "payer declined"). Only this route reaches it; a date never does. Code: `confirmed_unpaid`. |
| **Delayed cash** | Still payable under the rules but not yet paid: unsubmitted inside its deadline, rejected inside its correction window, or submitted and unpaid for more than 30 days `[P]`. |
| **Administrative time** | Staff minutes per week spent finding and chasing the above. Measured in minutes, never converted to dollars inside the product. |

## 5. Competitors, evidence, counterargument

| Alternative | Price (CAD, per month, one location) | Finding on 2026-11-10 | Status |
|---|---|---|---|
| Jane Insurance Billing add-on | 20 + 5 per additional full-time practitioner (2.50 part-time); for 8 full-time practitioners 20 + 7 × 5 = **55** `[D]`, on top of a Practice (79) or Thrive (99) plan | Verified. Add-on not available on the Balance plan (59). The brief's "plans 59–99" is correct. | `[S: SRC-01]` |
| ICBC HCPIR / HCPP | 0 (no charge stated) | Verified features in 4.3. Not in the brief; added. | `[S: SRC-15]` |
| WorkSafeBC My Provider Services | 0 (no charge stated on the page) | Real-time validation verified. The brief had this from a search summary. | `[S: SRC-22]` |
| Clinicmaster | Not public; quote after demo | Verified: pricing "tailored to your clinic group"; funders listed include WCB and Teleplan; ICBC and WorkSafeBC are not named on the page. Not available to Jane clinics `[C]`. | `[S: SRC-28]` |
| TELUS eClaims | Unverified | Page returned HTTP 403. The brief's "free, extended health only" stays unverified. | no source consulted |
| ClaimCheck Rehab pilot | **89** `[C]` | 1.6 × the Jane add-on for the 8-practitioner example (89 / 55) `[D]`. The chat's rationale: an add-on beside Jane "cannot cost much more than a Jane base plan (79-99)" `[C]`. | — |

- **Vendor-advertised versus measured:** everything in 4.2 and 4.3 is what vendors and payers say their tools do. No measured customer outcome exists for any of them, or for this product.
- **Strongest supporting evidence:** PR-01, PR-07 and PR-08 are hard, dated deadlines in the payers' own documents, and both payers changed physiotherapy rules or fees in 2026. WorkSafeBC states that incorrect or missing fee codes "are among the most common reasons for delays in payment" `[S: SRC-23]`.
- **Strongest counterargument:** a clinic that invoices weekly never meets a 45-day or 90-day deadline, Jane already surfaces WorkSafeBC rejections daily, and ICBC blocks over-limit invoices itself. In that clinic the product finds nothing, and the modelled benefit `[C, assumption]` (2% of 400 visits lost at CAD 85 = CAD 680 a month, half recovered = CAD 340) does not exist. The chat names this as the failure mode: "Audits show clinics lose very little, so nobody pays" `[C]`.

## 6. Minimum authorized pilot data

Field-level detail is in [schema.md](schema.md#2-minimum-authorized-pilot-data). Summary:

| Question | Answer |
|---|---|
| What is needed (the one definition, C1) | **The same two Jane exports for the free audit and for every weekly import** `[P]`: (1) the **Sales** report's invoice lines for ICBC and WorkSafeBC, with a date range starting **365 days before the export date** `[P]`, and (2) the **Insurance Policies** report `[S: SRC-08]` `[S: SRC-09]`. From the Sales lines the product keeps the *look-back set*: service in the last 90 days, plus every older line still unsubmitted, rejected, submitted and unpaid, partly paid or in an unknown state (so an older WorkSafeBC rejection still inside its PR-08 window is included whatever its service date). A "last 90 days" export alone is not enough. **Columns needed:** invoice number, date of service, **payer**, billing code, amounts invoiced and **paid** (the payment outcome), claim-submission state and its date, practitioner (turned into a discipline); and from Insurance Policies: claim number, status, end date, number of treatments, policy maximum, next appointment date, date of crash or injury. 16 fields; two of them (state date, date of crash or injury) only if Jane exports them. **Not in the 16 fields:** the *original submission date* and the *first rejection date*. The state date is the date of the last change only; the product derives bounds for the first rejection from weekly snapshots (B1-010) and asks staff to confirm the exact date in Teleplan or ICBC's portal. Adding either field needs the owner's written approval (open decision OD-3, [section 16](#16-open-decisions-for-the-owner)). **Jane's "Submitted" state does not prove that the payer received, accepted or will pay the invoice:** for ICBC it is a manual mark; only a recorded payment (or a portal check) does. |
| What is dropped before upload | Patient name, date of birth, PHN, address, phone, email, adjuster name, email and phone, policy notes, diagnosis and injury codes, practitioner name, chart content. |
| What leaves the clinic (C1, exact) | After minimisation, exactly these 16 fields and two ordinals, per row ([schema.md](schema.md#2-minimum-authorized-pilot-data)): Jane invoice number (**in clear**), date of service, payer (ICBC / WSBC / OTHER / UNKNOWN), billing code (mapped), amount invoiced, amount paid, submission state (closed list), state date, discipline (physiotherapy / support / other), claim token (keyed token, not the claim number), policy status (open / closed / other), policy end date, number of treatments, policy maximum, next appointment date, date of crash or injury; plus `row_no` and `line_no`. These are pseudonymised personal information: the clinic can re-link them, and the invoice number lets anyone with Jane access find the patient. Nothing else is sent. **Where they are hosted:** Phase 0, on an encrypted drive or in a storage bucket in AWS ca-central-1 (Montreal, 7 days), then on one encrypted laptop in Vancouver; application (proposed, not deployed), AWS ca-central-1 for the database, the import payload store (24 hours, AD-11), backups and email `[P]`. In the B2 development build they sit only in a local PostgreSQL database and a local MinIO store on the developer's machine, with synthetic rows. The wording "patient data stays in the clinic" or "never leaves" is not used for these fields. |
| What is pseudonymised before it leaves the clinic | Claim or policy number: in the application, a keyed token computed in the clinic's browser with a key the server never receives; in Phase 0, a sequential code (C0001, C0002, …) assigned by a spreadsheet that stays on the clinic's computer, with the code table never leaving the clinic. Practitioner name becomes a discipline in both. The Jane invoice number stays in clear so staff can find the visit in Jane. |
| Still personal information? | Yes. Tokenised billing rows can be re-linked by the clinic and are treated as personal information throughout `[A]`. |
| Clinic's authority to share | PIPA s. 18(2): an organization may disclose to another organization without consent if the individual consented to the original collection and the disclosure is solely for the purposes of that collection and "to assist the other organization to carry out work on behalf of the first organization"; the clinic stays responsible under s. 4(2) `[S: SRC-25]`. Billing a patient's insurer and getting paid is the collection purpose `[A]`. Lawyer review is task T-0.1.3. **C2 (2026-11-11): answered by [compliance/self-check.md](compliance/self-check.md) section 2 (with sections 5–7), owner sign-off recorded ([section 16](#16-open-decisions-for-the-owner), C2 decision).** s. 18(2) is a reasonable basis but not certain; the ICBC and WorkSafeBC contracts (SRC-43, SRC-44) make sending rows depend on the payers' written approval, so the no-lawyer model keeps rows at the clinic (OD-5). |
| What the founder may not do | Use clinic rows for anything other than that clinic's audit and weekly list: no product analytics on rows, no test fixtures from real rows, no cross-clinic benchmarks except counts the clinic agrees to publish. |
| Where processed and stored | Phase 0: prepared on the clinic's own computer; carried on an encrypted drive or uploaded to a storage bucket in AWS ca-central-1; worked on one encrypted laptop in Vancouver with no cloud sync; never sent by email ([Phase 0 data procedure](execution-plan.md#phase-0-data-procedure)). Application: AWS ca-central-1 (Montreal) for database, backups and email `[P]`, matching the chat's "stored in Canada under a PIPA agreement" `[C]`. PIPA as read contains no data-residency rule `[S: SRC-25]`; the commitment is contractual. |
| Retention | Free audit: deleted 30 days after the report unless the clinic converts. Subscription: for the term plus 30 days. Backups expire after 35 days. Phase 0 transfer bucket: 7 days. All `[P]`, under PIPA s. 35(2) `[S: SRC-25]`. |
| Deletion | On the owner's request or at termination, within 7 days, with a written confirmation listing row counts `[P]`. |

Not opened, and therefore open: ICBC's Health Care Services Terms and the WorkSafeBC Physiotherapy Services Agreement (either may restrict passing claim information to a contractor), the physiotherapy college's privacy standard, and guidance from the BC privacy commissioner. Task T-0.1.3 closes these before any export is accepted.

**C2 (2026-11-11): all four opened and answered by [compliance/self-check.md](compliance/self-check.md), owner sign-off recorded.** ICBC's Health Care Direct Billing Terms Schedule B (SRC-43; the old Services Terms PDF returns 404) puts ICBC claim records under FIPPA and allows transmission over the Internet only if "approved by ICBC in advance or contemplated under the Agreement" (s. 8(h)); WorkSafeBC's Physiotherapy Services Agreement (SRC-44) forbids disclosure of claim information to a third party without written consent unless necessary (s. 9.4), requires Canada-only storage including email and backup servers (Schedule D s. 15) and covers aggregated and de-identified data (s. 12); the College standard (SRC-42) says disclose "only with consent, unless required by law"; OIPC guidance (SRC-37 to SRC-40): PIPA has no mandatory breach notification. Consequence `[P]` (OD-5): the check runs on the clinic's computer and only a clinic-level summary leaves (self-check section 9); the 16 fields above leave only after the written payer approvals of self-check section 9.4.

## 7. Offer, pilot and what the price buys

**The chat's offer, verbatim (translated from Roman Urdu) `[C]`:** "Offer: a free audit of the last 90 days, then CAD 89 a month." The research note adds `[C]`: "Free 90-day look-back audit, then 89 CAD per month for 3 months, cancel any time."

| Item | Decision |
|---|---|
| Free step | One look-back audit of the last 90 days `[C]` from the **same two Jane exports as the weekly list** ([section 6](#6-minimum-authorized-pilot-data); C1: an earlier line here said "one export"), minimised at the clinic, done by hand, delivered as a one-page report with each class on its own line `[P]`. The look-back set adds every older ICBC or WorkSafeBC invoice still unsubmitted, rejected or unpaid `[P]`: the WorkSafeBC deadline is itself 90 days, so a 90-day window alone cannot show one being missed, and a WorkSafeBC rejection stays correctable up to the later of 180 days from service and 90 days from the first rejection. The report says, for each item, whether the export settles it (for example a payment) or staff must confirm it in the payer's portal (original submission date, first rejection date, ICBC's outcome on a late invoice). |
| Pilot | 3 months at CAD 89 a month, cancel any time `[C]`. Pilot duration 90 days. |
| What CAD 89 buys `[P]` | One location; a weekly list every Monday of ICBC and WorkSafeBC physiotherapy visits at risk and unpaid, each with the rule and the date; a monthly one-page measurement. Delivered by hand from a spreadsheet until the application exists, then by the application at the same price. |
| When paid `[P]` | Monthly in advance by card or e-transfer; first invoice on the day the first weekly list is delivered. |
| Who signs, pays, supplies | Owner signs the pilot and data agreement and pays; front desk supplies two exports each week. |
| Success metric | **Rescued near-limit cash**, defined in [PRD.md](PRD.md#11-success-metrics) as M-01, with the ICBC past-deadline and loss rates (M-02, lines kept apart), delayed cash (M-03) and administrative time (M-04) reported beside it, each on its own evidence and never added together. |
| Objective success and refund criterion `[P]` | By day 90, payer payments observed in the clinic's own exports on **near-limit** items total at least CAD 267 (= 3 × 89 `[D]`). An item is near-limit only if it was still unsubmitted, or rejected and uncorrected, with 14 or fewer days left to its payer limit or after it ([PRD.md](PRD.md#11-success-metrics)). A clinic that invoices ICBC within 30 days and corrects WorkSafeBC rejections promptly has no such items, so the test fails and the refund is due: the test can fail. If it fails and the clinic supplied at least 10 of the 13 weekly exports, the third month's CAD 89 is refunded. The test is computed from exports, so neither side can change the result by assertion. |
| Step to a recurring account | At day 90 the owner sees the measurement and chooses a tier by volume ([section 8](#8-price-reconciliation)); billing continues monthly; no new contract. |
| Sales cycle | 21 days `[C, assumption]`. |

## 8. Price reconciliation

Chat prices `[C]`: CAD 59 / 119 / 249; launch price 89; minimum 39; annual discount 15%; no setup fee; no usage fee. The chat did not say what separates the tiers or reconcile them with the assumed revenue of CAD 95 per account.

| Tier | Price | Proposed boundary `[P]` |
|---|---|---|
| Starter | 59 | Up to 150 ICBC and WorkSafeBC visits a month |
| Pro | 119 | 151–500 visits a month (the chat's 8-practitioner, 400-visit example) |
| Business | 249 | Over 500 visits a month |

- **Mix implied by CAD 95 `[D]`:** 55% Starter, 38% Pro, 7% Business gives 0.55 × 59 + 0.38 × 119 + 0.07 × 249 = 32.45 + 45.22 + 17.43 = **95.10**. The mix is an assumption `[A]`; no clinic volume data exists.
- **Pilot versus model `[D]`:** each account pays 89 for its first three months, 6 less than 95, so the model overstates first-quarter revenue by 3 × 6 = CAD 18 per account.
- **Usage in the cost notes `[C, assumption]`:** AI at CAD 1.50 covers reading about 30 remittance PDFs a month; support at CAD 8 is 15 minutes a month, which implies CAD 32 an hour `[D]`. The pilot design reads no PDFs ([TRD.md](TRD.md#ai-functions)); the CAD 1.50 stays in the model unspent, so the gross margin below is slightly conservative.

## 9. Unit economics

All amounts CAD, per month, per account unless stated. No foreign currency is used; the chat's USD and AED prices are "estimates for markets that are not relevant" `[C]`.

### 9.1 Inputs (all assumptions carried from the chat)

| Input | Value |
|---|---|
| Revenue per account | 95 |
| Variable cost | AI 1.50, hosting 2.00, storage 0.50, messaging 0.50, support 8.00, other 1.00 = 13.50; payment 2.9% × 95 + 0.30 = 3.055; total **16.555** `[D]` |
| Fixed cost excluding founder | 700 |
| Founder compensation | 6,000 |
| Acquisition cost (CAC) | 300 **per converted paying account**, cash only. This is the only CAC definition used in the repository. |
| Monthly churn | 3.5% |

### 9.2 Gross profit, payback, lifetime value

- Gross profit = 95 − 16.555 = **78.445** (82.6%) `[D]`. The chat rounded to 83% and the brief shows 78.44.
- Payback = 300 / 78.445 = **3.82 months** `[D]`.
- Lifetime value = 78.445 / 0.035 = **CAD 2,241** `[D]`.

### 9.3 Costs kept apart

| Kind | Amount | Note |
|---|---|---|
| Startup, cash (Phase 0, months 1–3) | Outreach 1,620 `[D]` (675 + 675 + 270 from [section 9.6](#96-cash-during-the-acquisition-ramp)) + legal review of the data agreement 1,500 `[A]` (C2: no lawyer is engaged; the figure is kept until OD-6 is decided) + fixed cost 3 × 700 = 2,100 `[C, assumption]` + contingency 280 `[A]` = **5,500, the Phase 0 cap**. Planned spend is 5,220; gross profit of 523 from the first accounts brings the net to 4,697 `[D]` | The 700 a month is charged from month 1 as in the ramp; it is an upper bound, because little hosting exists before the build. The chat's "about 1,200 CAD" was a 30-day budget and its outreach budget was 600 a month `[C]`; the ramp uses 675 (2.25 accounts × CAC 300), a difference of 75 a month kept so that CAC stays at 300. An earlier draft stated a cap of 3,500 that left out the fixed cost (finding F-006). |
| Startup, founder time | 120 hours at CAD 100 = 12,000 `[C, assumption]` | The author's task estimates in [execution-plan.md](execution-plan.md#effort-summary) come to 356–574 hours; the chat's 120 hours does not cover the build as specified. |
| Monthly fixed | 700, or 6,700 with founder | |
| Variable | 16.555 per account | |
| Initial acquisition | 300 per new account | |
| Churn replacement | 0.035 × 300 = **10.50** per account per month `[D]` | |

### 9.4 Operating break-even

Contribution after churn replacement = 78.445 − 10.50 = **67.945** `[D]`.

| Case | Arithmetic | Accounts |
|---|---|---|
| Without founder | 700 / 67.945 = 10.30 | **11** (matches the chat) |
| With founder | 6,700 / 67.945 = 98.61 | **99** (matches the chat) |

### 9.5 Pilot economics

At 89: payment cost 2.9% × 89 + 0.30 = 2.881; gross profit 89 − 13.50 − 2.881 = **72.619** `[D]`; three pilot months give 217.86, which does not repay the CAD 300 acquisition cost until month 5 `[D]`. A refund under [section 7](#7-offer-pilot-and-what-the-price-buys) costs at most 89 per account.

### 9.6 Cash during the acquisition ramp

Model `[D]`: outreach of 250 distinct clinics a month `[C]`; each month of outreach yields 250 × 0.08 × 0.45 × 0.25 = 2.25 new accounts the following month (21-day cycle); accounts(t) = accounts(t−1) × 0.965 + new(t); acquisition spend = new accounts generated × 300 (675 for a full month); fixed 700. **Month 1 is December 2026.** Until the build is released (Phase 6; April 2027 at the earliest, and only with two developers) pilots are served by hand. The base case caps the pool at 600 clinics `[A]` ([section 10](#10-funnel-from-distinct-reachable-prospects)).

**Base case (pool 600, revenue 95, churn 3.5%, CAC 300)**

| Month | Outreach | New | Accounts | Revenue | Gross profit | Acquisition | Net, no founder | Cumulative, no founder | Net, with founder | Cumulative, with founder |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 Dec 2026 | 250 | 0.00 | 0.00 | 0 | 0 | 675 | −1,375 | −1,375 | −7,375 | −7,375 |
| 2 | 250 | 2.25 | 2.25 | 214 | 177 | 675 | −1,198 | −2,573 | −7,198 | −14,573 |
| 3 | 100 | 2.25 | 4.42 | 420 | 347 | 270 | −623 | −3,197 | −6,623 | −21,197 |
| 4 | 0 | 0.90 | 5.17 | 491 | 405 | 0 | −295 | −3,491 | −6,295 | −27,491 |
| 5 | 0 | 0.00 | 4.99 | 474 | 391 | 0 | −309 | −3,800 | −6,309 | −33,800 |
| 6 | 0 | 0.00 | 4.81 | 457 | 377 | 0 | −323 | −4,123 | −6,323 | −40,123 |
| 7 | 0 | 0.00 | 4.64 | 441 | 364 | 0 | −336 | −4,459 | −6,336 | −46,459 |
| 8 | 0 | 0.00 | 4.48 | 426 | 351 | 0 | −349 | −4,807 | −6,349 | −52,807 |
| 9 | 0 | 0.00 | 4.32 | 411 | 339 | 0 | −361 | −5,168 | −6,361 | −59,168 |
| 10 | 0 | 0.00 | 4.17 | 396 | 327 | 0 | −373 | −5,541 | −6,373 | −65,541 |
| 11 | 0 | 0.00 | 4.03 | 382 | 316 | 0 | −384 | −5,925 | −6,384 | −71,925 |
| 12 Nov 2027 | 0 | 0.00 | 3.89 | 369 | 305 | 0 | −395 | −6,320 | −6,395 | −78,320 |

Reading: the base case peaks at **5.17 accounts** and never reaches the 11 needed. There is no cash trough; the deficit grows every month: **CAD 6,320 without founder pay and CAD 78,320 with it after 12 months** `[D]`.

**Downside case `[A]`:** reply 5%, meeting 35%, close 15% (0.2625% of outreach, 0.656 accounts per 250), all accounts on Starter at 59, churn 6%, same CAD 675 monthly outreach spend, so CAC = 675 / 0.656 = **1,029** `[D]`. Gross profit = 59 − 13.50 − (0.029 × 59 + 0.30 = 2.011) = **43.489** (73.7%). Churn replacement = 0.06 × 1,028.57 = 61.71, larger than gross profit: **no break-even exists** `[D]`.

| Month | Outreach | New | Accounts | Revenue | Gross profit | Acquisition | Net, no founder | Cumulative, no founder | Cumulative, with founder |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 250 | 0.00 | 0.00 | 0 | 0 | 675 | −1,375 | −1,375 | −7,375 |
| 2 | 250 | 0.66 | 0.66 | 39 | 29 | 675 | −1,346 | −2,721 | −14,721 |
| 3 | 100 | 0.66 | 1.27 | 75 | 55 | 270 | −915 | −3,636 | −21,636 |
| 4 | 0 | 0.26 | 1.46 | 86 | 63 | 0 | −637 | −4,273 | −28,273 |
| 6 | 0 | 0.00 | 1.29 | 76 | 56 | 0 | −644 | −5,557 | −41,557 |
| 12 | 0 | 0.00 | 0.89 | 52 | 39 | 0 | −661 | −9,484 | −81,484 |

(Months 5 and 7–11 omitted; each continues the same recurrence.)

**If the pool were unlimited** (it is not): accounts converge to 2.25 / 0.035 = **64.3**, still below 99; the 10.30 accounts needed without founder pay are passed in month 6 (10.49) and the rounded 11 in month 7 (12.37), the monthly result turns positive in month 10, the cumulative trough is **CAD 6,514 in month 9** and cumulative cash turns positive in month 21; with founder pay the deficit is CAD 78,109 at month 12 and still growing at month 24 (CAD 138,780) `[D]`.

**Plain statement:** on the chat's inputs this is at best a side business that covers its own CAD 700 a month. It cannot pay a CAD 6,000 founder salary from cold outreach to BC physiotherapy clinics. It becomes a business only if the audits show a loss large enough to support Pro pricing and a much higher close rate, or if a partner channel (PABC, bookkeepers `[C]`) replaces cold outreach.

### 9.7 Thresholds (not forecasts)

With founder pay and 250 clinics a month, break-even requires steady-state accounts ≥ 99, so new accounts per month ≥ 99 × 0.035 = 3.47 at CAD 300 `[D]`, a 1.39% outreach-to-paid rate instead of 0.9%, sustained on about 3,000 distinct clinics a year.

## 10. Funnel from distinct reachable prospects

- **Chat funnel `[C, assumption]`:** "250 → 20 → 9 demos → 2 customers": reply 8%, meeting 45%, close 25%, so 250 × 0.08 = 20; 20 × 0.45 = 9; 9 × 0.25 = 2.25. One paying account per 111 clinics contacted `[D]`.
- **Needed `[D]`:** 11 accounts need 11 / 0.009 = 1,222 distinct clinics before churn; 99 need 11,000.
- **Pool: unknown.** No source consulted gives the number of BC physiotherapy clinics that use Jane, have four or more practitioners and bill ICBC or WorkSafeBC for 20% of visits. **Primary counts, C1 (2026-11-11):** Statistics Canada table 33-10-1174-01 ("Canadian Business Counts, with employees, June 2026") gives **1,088 BC locations with employees** in NAICS 621340, offices of physical, occupational and speech therapists and audiologists (so not physiotherapy alone), of which **475 have 5 to 49 employees** (262 + 164 + 49 `[D]`) `[S: SRC-32]`; locations without employees are in another table, not pulled. The College of Health and Care Professionals of BC counts **5,621 Full-class physical therapists** at 31 March 2026 (5,904 with 283 Student registrants; the Student class ended on 1 April 2026) `[S: SRC-33]`. Neither count says how many clinics use Jane or bill ICBC and WorkSafeBC. An earlier primary figure: "over 370 clinics" representing "over 3,500 practitioners" had signed up for ICBC's provider locator by March 2025, across all seven disciplines and all of BC `[S: SRC-16]`. The PABC directory and the College register `[C]` and WorkSafeBC's contracted-provider lists `[S: SRC-24]` were not counted. The chat's research says "the market is a few thousand clinics" `[C]` without a source.
- **Scenario used `[A]`:** 600 distinct reachable clinics that fit the profile. **This remains an assumption:** it is not derived from the counts above (600 is 55% of the 1,088 employer locations of all four professions and more than the 475 with 5–49 employees `[D]`); T-0.1.4 must count it. At 0.9% that is 5.4 paying accounts in total, the base case above. Task T-0.1.4 replaces 600 with a counted list; if the count is under 1,222 the product cannot reach break-even from this channel at these rates, and the count is reported to the portfolio owner before any build.

## 11. Stop rule

### 11.1 The chat's rule, exactly as stated

Chat answer, verbatim (translated) `[C]`: "When to stop: if in the first 5 audits the loss comes out below CAD 150 a month." Research record `[C]`: "Stop if the first 5 audits find under 150 CAD a month of at-risk revenue per clinic, or if fewer than 2 of 10 audited clinics pay." Also in the record `[C]`: a week-2 gate of "median finding above 300 CAD a month", and "if 5 audits show under 1% of ICBC and WorkSafeBC visits at risk, drop it."

### 11.2 Checks on the chat's rule

1. **Three thresholds, not one.** CAD 150, CAD 300 and 1% are all in the record. For the chat's 400-visit example 1% of visits at CAD 85 is CAD 340 `[D]`, so the three disagree.
2. **"Below 150 in the first 5" does not say mean, median or each.**
3. **"At-risk revenue" is not the decisive question.** Revenue at risk that Jane's workflow would have caught anyway is not recoverable by this product.
4. **False stop on the payment test.** If the assumed 25% close rate is exactly true, the number of payers among 10 audited clinics is Binomial(10, 0.25): P(0 or 1) = 0.75¹⁰ + 10 × 0.25 × 0.75⁹ = 0.0563 + 0.1877 = **24.4%** `[D]`. The rule would kill a product performing exactly as assumed about one time in four.
5. **The payment test is weak at middling close rates.** With 16 audits and "fewer than 2 pay", the rule stops with probability 51.5% if the true close rate is 10%, 38.8% at 12.5% and 28.4% at 15% `[D]`. A pass at exactly 2 of 16 (12.5%) means CAC = 675 / 1.125 = 600, contribution 78.445 − 21 = 57.445 and break-even at 13 accounts without founder pay and 117 with it `[D]`.
6. **False stop on the amount test** cannot be computed without a distribution of findings. Illustration `[A]`: if each audit independently has a 70% chance of finding CAD 150 or more, the median of 5 falls below 150 when at most 2 of 5 reach it: **16.3%** `[D]`.
7. **Timing.** 10 audits need 10 / (0.08 × 0.45) = 278 clinics contacted `[D]`, about five weeks at 58 a week, then 21 days to pay: the chat's rule cannot be read before about week 8.

### 11.3 Proposed revision `[P]` — a change to the chat's rule, not a restatement

Stop, and do not build, if **either** holds once 16 clinics have been audited and each has had 30 days to pay:

- **Amount:** **both** of these medians across the 16 audits are under CAD 150 a month. They are computed separately and never added:
  - *Permanent loss per month* = CAD of ICBC physiotherapy visits with service dates from 90 to 46 days before the audit date that passed PR-01 unsubmitted or fall under PR-03, divided by 1.5 (the cohort is 45 days, 1.5 months). Certain and discretionary amounts are shown on separate lines inside this figure. **Inconsistency found in C1 (2026-11-11), not resolved here:** the PR-01 part of this figure is not a loss: past the 45 days ICBC "may" not pay, at its discretion `[S: SRC-12]` §6.1. The product now reports it as *past payer deadline – payment at ICBC's discretion*, with *confirmed unpaid* (ICBC's recorded outcome) as a third line; the code computes all three lines separately and the gate arithmetic above is unchanged. `[P]` proposal for the owner (OD-1, [section 16](#16-open-decisions-for-the-owner)): rename the figure "Past-deadline and ineligible ICBC amounts per month", keep it as the gate's first figure, and show in the memo how many of its CAD are confirmed unpaid.
  - *Near-limit delayed cash per month* = for each rule, the CAD balance of near-limit items ([PRD.md](PRD.md#11-success-metrics)) still collectable on the audit date, divided by the length in months of the band of dates that can hold such items, then summed (all three are delayed cash). The bands `[D]`: ICBC-01, service dates 31 to 45 days before the audit, 15 days; WSBC-01, service dates 76 to 90 days before, 15 days; WSBC-02, correction limits falling 0 to 14 days after the audit, 15 days. With a 30-day month `[A]` each band is 15 / 30 = 0.5 month, so the monthly figure = balance / 0.5 = balance × 2. This assumes items enter the band at a steady rate `[A]`. Example `[D]`: three ICBC Standard Treatments in the band are 3 × 97 = 291; 291 / 0.5 = CAD 582 a month. The CAD 150 threshold therefore equals a balance of 150 × 0.5 = CAD 75 in the band, and one Standard Treatment in the band gives 97 × 2 = CAD 194 a month: a clinic's figure moves in steps of about 194, which is why the test is on the median of 16 clinics and not on any one. An earlier draft divided by 3 (a 90-day window) and so understated this figure sixfold (3 / 0.5 = 6), biasing the gate toward a false stop; corrected after the reviewer's retest.
  - WorkSafeBC amounts past PR-07 (payment at WorkSafeBC's discretion) and past the latest possible PR-08 limit ("cannot be paid") among the older open invoices are reported as two balances with no monthly conversion and do not enter the test.
  - Administrative time is reported in minutes and does not enter the test; or
- **Payment:** fewer than 2 of the 16 paid a first CAD 89 invoice.

Why 16: P(0 or 1 payers | 16, 0.25) = 0.75¹⁶ + 16 × 0.25 × 0.75¹⁵ = 0.0100 + 0.0535 = **6.3%** false stop `[D]`; if the true rate is 5% the rule stops with probability 81.1% `[D]`; its weakness between 10% and 15% is shown in 11.2 item 5. Because of that weakness, a pass with 2 or 3 payers `[P]` is recorded as a **weak pass**: the economics in section 9 are recomputed at the observed close rate and shown to the portfolio owner before the build starts. Sixteen audits need 16 / 0.036 = 444 clinics contacted `[D]`, 7.7 weeks at 58 a week, so the decision falls at the end of month 3 (February 2027), inside the Phase 0 cap. The chat's CAD 150 threshold is kept; what it measures is changed. **This is the only build gate in the repository;** [section 13](#13-what-buyer-evidence-would-change-the-decision) and [PRD.md section 13](PRD.md#13-evidence-that-would-justify-expanding-the-mvp) describe what happens after it, not other gates.

Early stop `[P]`: if in the first 5 audits **every** clinic is under CAD 50 a month on both figures, stop then. For near-limit delayed cash, under CAD 50 a month is a band balance under CAD 25 `[D]`, in practice no near-limit item at all.

## 12. Go-to-market plan

One set of numbers is used here, in [section 9.6](#96-cash-during-the-acquisition-ramp) and in [section 10](#10-funnel-from-distinct-reachable-prospects): 250 distinct clinics a month (58 a week), reply 8%, audit meeting 45%, close 25%, 21-day cycle, CAC 300.

- **Ideal customer profile.** Physiotherapy clinic, Metro Vancouver, on Jane with the Insurance Billing add-on, 4–25 practitioners, at least 20% of visits billed to ICBC or WorkSafeBC, a member of ICBC's Recovery Network, and the owner "can name a recent unpaid claim" `[C]`. Triggers `[C]`: a program-guide change, a year-end review, front-desk turnover. **Disqualified:** not on Jane; fewer than 4 practitioners; no direct billing to ICBC or WorkSafeBC; billing outsourced to a contractor who will not share exports; chiropractic-only or massage-only clinics until their rule sets are verified ([PRD.md](PRD.md#8-non-goals)); owner unwilling to sign the data agreement.
- **Named roles.** Feels the pain: front-desk lead or clinic manager. Signs and pays: owner. Can block: owner on privacy, external bookkeeper. Supplies sample data: front-desk lead.
- **Prospect list.** Sources `[C]`: PABC Find a Physio directory, the College public register, ICBC's provider locator, Jane community Facebook groups; added `[S: SRC-24]`: WorkSafeBC's contracted physiotherapy provider lists. Count: unknown ([section 10](#10-funnel-from-distinct-reachable-prospects)). Build (T-0.1.4): one row per clinic location; confirm Jane by the clinic's online-booking address (Jane booking sites use a `janeapp.com` sub-domain) `[A]`; confirm ICBC from the locator; remove duplicates by address; lead cost "about 100 CAD for 100 clinics" for an email finder `[C]`. **CASL (C2, [compliance/self-check.md](compliance/self-check.md) section 1):** an email may go only to an address the clinic itself published (or gave us), with its URL and date recorded; an address found or guessed by an email finder and not published by the clinic gives no implied consent (CASL s. 10(9)(b), SRC-34); proposal OD-7.
- **Channel and sequence.** First channel `[C]`: in-person and email outreach to owners with the free audit. Week 1: walk into 15 clinics `[C]`, before 9 am or after 2 pm, ask for the manager. Every week: 58 first-touch emails, one follow-up after 4 working days, one call to non-responders `[P]`. One founder, 15 hours a week (60 hours a month `[C]`). Backup channel `[C]`: PABC and BCCA newsletters, Jane community groups.
- **Message (synthetic).** Every message ends with the CASL footer of [compliance/self-check.md](compliance/self-check.md) section 10.3 (sender, mailing address, contact, unsubscribe within 10 business days).
  - First touch — Subject: unpaid ICBC and WorkSafeBC visits. "Hi Priya, I'm a Vancouver developer. ICBC now says invoices sent more than 45 days after a visit may not be paid, and WorkSafeBC stops paying a rejected invoice once its correction window closes, which can be 180 days after the visit. Jane lists your unsubmitted and rejected invoices and lets you filter them by date; it does not work out how many days each one has left. I'd like to run a free audit of Harbourview Physio's last 90 days, plus older invoices that are still open, and give you one page: what is past a payer deadline (ICBC may still pay those, at its discretion), what is close to a deadline, what can still be collected, and which items need a check in ICBC's portal or Teleplan. We would prepare two Jane exports together at your front desk in about 20 minutes. On your computer, patient names, birth dates and health numbers are removed and claim numbers are replaced by codes; what I receive is 16 billing fields per visit, including the Jane invoice number, dates of service and amounts. Nothing to install. If the page shows a real gap, the weekly version is CAD 89 a month for three months, cancel any time."
  - Follow-up — "Hi Priya, one detail on the free audit: I receive billing rows only (invoice number, visit date, payer, fee code, amounts, claim state and a few policy dates), never patient names, birth dates or health numbers; nothing is sent by email; the rows are kept in Canada (AWS Montreal or an encrypted drive) and my copy is deleted 30 days after I give you your page. Would Tuesday or Thursday at 2:30 suit a 15-minute call?"
- **Pilot offer and conversion.** [Section 7](#7-offer-pilot-and-what-the-price-buys).
- **Objections.**
  1. "Jane already tracks claims" `[C]`. Honest answer: it does. It files WorkSafeBC rejections daily, can alert at a visit maximum, and lets you filter unsubmitted and rejected invoices by date. What it does not do, as far as its guides show, is compute a deadline for each invoice across both payers, and it has no ICBC status feed. The free audit shows whether that matters in your clinic; if nothing is close to a deadline, do not buy.
  2. "We cannot share patient data" `[C]`. Honest answer: names, birth dates and health numbers are removed on your computer; claim numbers are replaced by codes whose table stays with you; the file is never emailed. What does leave is listed exactly in [section 6](#6-minimum-authorized-pilot-data): 16 billing fields per visit, including the Jane invoice number, visit dates and amounts, hosted in AWS ca-central-1 (Montreal) or on an encrypted drive and laptop in Vancouver, under a written agreement that makes me your contractor. It is still personal information and you remain responsible for it; here is the agreement and the one-page procedure.
  3. "Exports are a hassle" `[C]`. Honest answer: about 20 minutes the first time and 10 minutes a week by hand `[A]` (the chat said two minutes); the pilot measures the minutes and subtracts them from the time saved.
- **First 30, 60 and 90 days** (base case, pool 600) `[D]`:

| By day | Clinics contacted | Replies | Audits | New paying accounts (cumulative converted) | Cash spent (outreach + fixed + legal) | Founder hours |
|---|---|---|---|---|---|---|
| 30 | 250 | 20 | 9 | 0 (first conversions land in month 2) | 675 + 700 + 1,500 = 2,875 | 60 |
| 60 | 500 | 40 | 18 | 2.25 | 1,350 + 1,400 + 1,500 = 4,250 | 120 |
| 90 | 600 | 48 | 21.6 | 4.5 (4.42 after churn) | 1,620 + 2,100 + 1,500 = 5,220 (cap 5,500) | 180 |

  A further 0.9 converts in month 4, for 5.4 in total, the same as section 10. Weekly targets: 58 emails, 4–5 replies, 2 audits, and from week 5 one paid conversion every other week.
- **GTM stop rule.** [Section 11.3](#113-proposed-revision-p--a-change-to-the-chats-rule-not-a-restatement), plus a channel rule `[P]`: if after 250 clinics fewer than 8 reply (assumed 20), stop cold email and test the PABC route before spending more.
- **Items in the chat's research not used in this first test, recorded so they are not lost `[C]`:** the referral offer ("one free month for both clinics") is held until there are paying accounts to refer, and would cost up to 2 × 89 per referral; the LinkedIn connection and follow-up scripts are a third channel behind email and the association route; the "first 3" step (use the first audit's dollar findings as a one-page case study) is kept as part of T-0.3.3, with the clinic's written consent and no clinic name unless it agrees; the 30-day budget of CAD 600 is discussed in [section 9.3](#93-costs-kept-apart).

## 13. What buyer evidence would change the decision

| Evidence | Effect |
|---|---|
| The gate in 11.3 is passed, either median is CAD 300 or more a month, and 4 or more of 16 pay | Same build decision as 11.3; in addition, price new accounts at Pro. |
| Audits find losses but almost all already known to staff | The value is convenience only; re-price at 39–59 or stop. |
| Owners will not sign the data agreement even with minimisation | Stop, or switch to an on-site service with no data leaving the clinic. |
| Jane shows a deadline clock in a live account (T-0.1.2) | Gaps G-1 and G-2 close; stop unless G-3 to G-5 alone pass the amount test. |
| Counted pool under 1,222 | Cold outreach cannot reach break-even; continue only with a partner channel. |

## 14. Missing inputs

| # | Missing | Needed for | Task |
|---|---|---|---|
| 1 | Exact column headers of Jane's exports (Jane publishes none) | Import mapping | T-0.1.2 |
| 2 | Whether a Jane export carries claim-submission state dates, date of crash and date of injury | Rules that need those dates | T-0.1.2 |
| 3 | Counted reachable pool | Sections 9.6 and 10 | T-0.1.4 |
| 4 | Lawyer's reading of PIPA s. 18(2), the ICBC terms, the WorkSafeBC agreement and the college standard — **C2 (2026-11-11): answered by [compliance/self-check.md](compliance/self-check.md) sections 2, 5, 6, 7, owner sign-off recorded (section 16)** | Section 6 | T-0.1.3 |
| 5 | Real loss per clinic, split by class | Everything | T-0.3.2 |
| 6 | ICBC's normal time from invoice to payment (not found in any source read) | The 30-day unpaid threshold | T-0.3.2 |
| 7 | ICBC chiropractic and massage guides; WorkSafeBC chiropractic schedule | Rule sets beyond physiotherapy | T-1.1.1 |
| 8 | Location of the founder's own VPS `[C]` | Whether it may ever hold clinic data | T-2.1.4 |
| 9 | The format of Jane invoice numbers | The identifier guard ([TRD.md](TRD.md#import-handling)) | T-0.1.2 |
| 10 | Payer documents in force before 2026-04-01 | Checking older open invoices instead of listing them as "could not check" | T-1.1.1 |
| 11 | Whether the clinic records ICBC "Submitted" at the moment of keying or later | How often G-4 hides an unkeyed invoice | T-0.3.2 |
| 12 | Whether Jane can export the original submission date and the first rejection date (C1) | Exact PR-01 lateness and PR-08 limit without a portal check; OD-3 | T-0.1.2 |

## 15. Sources and assumptions

All consulted 2026-11-10 unless a row says 2026-11-11 (correction round C1). Jurisdiction BC, Canada unless stated. "Access" notes any restriction.

| ID | Source | Scope | Access |
|---|---|---|---|
| SRC-01 | Jane, pricing — https://jane.app/pricing | Plans 59 / 79 / 99; Insurance Billing add-on | Open. Per-licence prices for extra practitioners not shown. |
| SRC-02 | Jane guide, claim submissions and insurer portals — https://jane.app/guide/working-with-claim-submissions-and-online-insurer-portals | Billing states, portal link-out, Teleplan for WorkSafeBC | Open |
| SRC-03 | Jane guide, Teleplan (MSP & WorkSafeBC) rejections — https://jane.app/guide/rejections | Daily remittance fetch, Rejected folder | Open |
| SRC-04 | Jane guide, Teleplan rejection codes — https://jane.app/guide/teleplan-rejection-codes | WorkSafeBC codes J1, SJ, G4 | Open |
| SRC-05 | Jane guide, late submission reason code — https://jane.app/guide/teleplan-late-submission-reason-code | 90-day Teleplan rule | Open |
| SRC-06 | Jane guide, ICBC physiotherapy — https://jane.app/guide/icbc-physiotherapy | ICBC set-up, fees shown, maximum-treatments alert | Open. Undated; fee table "on or after May 1, 2025". |
| SRC-07 | Jane guide, billing WorkSafeBC physiotherapy — https://jane.app/guide/billing-to-worksafe-bc-physiotherapy | Required fields, fee codes, visit limits as Jane states them | Open |
| SRC-08 | Jane guide, Insurance Policies report — https://jane.app/guide/insurance-policy-report | Report fields, CSV export | Open. Full export column list not given. |
| SRC-09 | Jane guide, billing reports — https://jane.app/guide/billing-reports | Sales report contents | Open. No column names. |
| SRC-10 | Jane guide, Accounts Receivable report — https://jane.app/guide/accounts-receivable-report | Insurer balances over time | Open |
| SRC-11 | Jane guide, exporting reports — https://jane.app/guide/exporting-reports-and-customizing-them-in-excel | Excel export | Open |
| SRC-12 | ICBC, Physiotherapy program guide, effective 2026-09-27 — https://partners.icbc.com/assets/1RUX2CgKxuwdjUu9UNe83Y/physiotherapy-program-guide.pdf | PR-01 to PR-06 | Open PDF, 35 pages, text extracted and read. Re-opened 2026-11-11 (C1): s. 6.1 reads "At ICBC's sole discretion, invoices submitted outside of the 45-day timeframe may not be paid." |
| SRC-13 | ICBC, Fee Schedule for Health Care Providers CL534, effective 2026-09-27 — https://partners.icbc.com/assets/2wSkk2HQZJ9e3xvSXTSIhH/fee-schedule-health-care-providers.pdf | Fees from 2026-04-01 and 2026-09-27 | Open PDF |
| SRC-14 | ICBC, Health Services newsletter June 2025 — https://partners.icbc.com/assets/1hSfvIMVmiTzIgFmvYCDB1/health-services-newsletter-june2025.pdf | 45-day alert text | Open PDF. The brief had this as "secondary, not opened"; now opened. |
| SRC-15 | ICBC, invoicing and reporting — https://partners.icbc.com/health-services/invoicing-reporting | HCPIR, HCPP features | Open; some sections load dynamically and were not captured |
| SRC-16 | ICBC, Health newsletter March 2025 — https://partners.icbc.com/assets/7IW2I1r22eTxNB2u1tXyM7/newsletter-health-march-2025.pdf | 370 clinics, 3,500 practitioners | Open PDF |
| SRC-17 | ICBC, overview of 2026-09-27 program guide updates — https://partners.icbc.com/assets/1LAFiNFxSDv4ObaTYZUuH7/Overview%20of%20Sep%2027,%202026%20Program%20Guide%20changes.pdf | What changed in September 2026 | Open PDF |
| SRC-18 | ICBC, Health Services newsletter October 2025 — https://partners.icbc.com/assets/8ghioupJ3Lgyb76uy2XdX/health-services-newsletter-oct2025.pdf | Back-dating not permitted; five-business-day treatment-plan answer | Open PDF |
| SRC-19 | WorkSafeBC, Physiotherapy Services Reference Manual, **June 2026** (page date), used with the Physiotherapy Services Memorandum of Agreement and schedules effective 2026-04-01 — https://www.worksafebc.com/resources/health-care-providers/guides/physiotherapy-services-reference-manual?lang=en | PR-07 to PR-09, PR-12 | Open; PDF behind a download button; 55 pages, text extracted and read on 2026-11-10 and again on 2026-11-11 (C1). The PDF downloaded on 2026-11-11 was created 2026-06-26 and its footer still says "February 2026"; PR-07, PR-08, PR-09 and PR-12 unchanged, same pages. The Agreement was not opened |
| SRC-20 | WorkSafeBC, Physiotherapy Fee Schedule, 2026-03-23 — https://www.worksafebc.com/resources/health-care-providers/guides/standard-and-post-surgical-physiotherapy-fee-schedules?lang=en | PR-10, PR-11 | Open; watermarked "for reference only"; Schedule B of the Agreement governs |
| SRC-21 | WorkSafeBC, invoice corrections — https://www.worksafebc.com/en/health-care-providers/billing-and-reporting/invoice-corrections | Correction letters and tool | Open; page dated 2020-11-25 |
| SRC-22 | WorkSafeBC, online billing options — https://www.worksafebc.com/en/health-care-providers/billing-and-reporting/online-billing-options | Real-time validation | Open |
| SRC-23 | WorkSafeBC, billing and reporting — https://www.worksafebc.com/en/health-care-providers/billing-and-reporting | Fee-code errors as a cause of delay | Open |
| SRC-24 | WorkSafeBC, musculoskeletal physiotherapy services — https://www.worksafebc.com/en/health-care-providers/provider-types/physiotherapists/physiotherapy-services | Teleplan or My Provider Services; links | Open |
| SRC-25 | Personal Information Protection Act, SBC 2003, c. 63 — https://www.bclaws.gov.bc.ca/civix/document/id/complete/statreg/03063_01 | ss. 4, 6, 8, 10, 11, 12, 14, 18, 23, 34, 35 (C2 also ss. 1, 3, 5, 7, 56, 57) | Open. No breach-notification or data-residency provision in the text read. Re-opened 2026-11-11 (C2): "current to November 3, 2026", still none. |
| SRC-26 | OWASP ASVS 5.0.0 — https://github.com/OWASP/ASVS/tree/v5.0.0/5.0/en | Requirements cited in [TRD.md](TRD.md#security-requirements-targeted) | Open |
| SRC-27 | W3C, WCAG 2.2 — https://www.w3.org/TR/WCAG22/ | Criteria cited in [design.md](design.md#8-accessibility-map) | Open |
| SRC-28 | Clinicmaster — https://www.clinicmaster.com | Pricing stance, funders named | Open |
| SRC-29 | TELUS eClaims — https://www.telus.com/en/health/health-professionals/allied-healthcare-professionals/eclaims | — | **Blocked (HTTP 403).** Claims about it are unverified. |
| SRC-30 | WorkSafeBC bulletin 2026-41 (2026-04-20), rejected invoices for chiropractic Form 8C — https://www.worksafebc.com/resources/health-care-providers/bulletins/2026-41-rejected-invoices-for-form-8c-chiropractic-first-report-submissions?lang=en | Title and date only | Body PDF not read; stays secondary |
| SRC-32 | Statistics Canada, table 33-10-1174-01, Canadian Business Counts, with employees, June 2026 — https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3310117401 | BC, NAICS 621340: 1,088 locations with employees; 1–4: 606; 5–9: 262; 10–19: 164; 20–49: 49; 50–99: 6; 100–199: 1 | Open; full CSV downloaded and read 2026-11-11 (C1). Employer locations only; NAICS 621340 also covers occupational and speech therapists and audiologists |
| SRC-33 | College of Health and Care Professionals of BC, 2025/26 Impact Report — https://chcpbc.org/wp-content/uploads/2026/07/2025-26-CHCPBC-Impact-Report.pdf | Physical therapy registrants at 31 March 2026: 5,621 Full, 283 Student, 0 Temporary, total 5,904 | Open PDF, read 2026-11-11 (C1). Student classes ended 2026-04-01 |
| SRC-34 | CASL, S.C. 2010, c. 23 — https://laws-lois.justice.gc.ca/eng/acts/E-1.6/FullText.html | ss. 6, 10, 11, 12, 13, 20 | Open 2026-11-11 (C2), current to 2026-10-19 |
| SRC-35 | CRTC Electronic Commerce Protection Regulations, SOR/2012-36 — https://laws-lois.justice.gc.ca/eng/regulations/SOR-2012-36/FullText.html | ss. 2, 3 (sender identification, unsubscribe) | Open 2026-11-11 (C2). The CRTC CASL FAQ page was blocked (HTTP 403) |
| SRC-36 | Electronic Commerce Protection Regulations, SOR/2013-221 — https://laws-lois.justice.gc.ca/eng/regulations/SOR-2013-221/FullText.html | ss. 3, 4 (business-to-business and referral exclusions) | Open 2026-11-11 (C2) |
| SRC-37 | OIPC BC, Privacy breach quick reference guide for small and medium-sized businesses — https://oipc.bc.ca/documents/guidance-documents/3134 | Four breach steps | Open PDF (created 2026-04-20), 2026-11-11 (C2) |
| SRC-38 | OIPC BC, PIPA and AI scribes: best practices for healthcare organizations in BC — https://www.oipc.bc.ca/documents/guidance-documents/3082 | Responsibility for vendors; disclosure outside Canada; vendor questions | Open PDF (created 2026-01-27), 2026-11-11 (C2) |
| SRC-39 | OIPC BC, Privacy breaches: tools and resources for the private sector — https://www.oipc.bc.ca/documents/guidance-documents/1361 | Notification factors and timeline | Open PDF (created 2026-03-17), 2026-11-11 (C2) |
| SRC-40 | OIPC BC, BC Physician Privacy Toolkit, 3rd ed., August 2017 — https://www.oipc.bc.ca/documents/guidance-documents/1400 | Service-contract elements; Canada storage recommended; no PIPA breach-report duty | Open PDF, 2026-11-11 (C2); written for physicians, used by analogy |
| SRC-41 | OPC Canada, Interpretation Bulletin: Personal Information (modified 2013-10-11) — https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/pipeda-compliance-help/pipeda-interpretation-bulletins/interpretations_02/ | "Serious possibility" identifiability test, *Gordon v. Canada (Health)*, 2008 FC 258 | Open 2026-11-11 (C2); federal, persuasive only in BC |
| SRC-42 | CHCPBC, Ethics and Practice Standards, effective 2026-04-01 — https://chcpbc.org/wp-content/uploads/2026/04/Ethics-and-Practice-Standards.pdf | Privacy and Confidentiality 1–7; Records 6.1, 9.1 | Open PDF, 2026-11-11 (C2) |
| SRC-43 | ICBC, Health Care Direct Billing Terms, last updated 2025-11-01 — https://www.icbc.com/policies/health-care-direct-billing-terms | ss. 9.1–9.6; Schedule B ss. 4–14 | Open 2026-11-11 (C2). The older Health Care Services Terms PDF (partners.icbc.com) returned HTTP 404 |
| SRC-44 | WorkSafeBC, Physiotherapy Services Agreement, effective 2026-04-01 — https://www.worksafebc.com/resources/health-care-providers/guides/physiotherapy-services-agreement?lang=en&direct= | ss. 2.5, 9.1–9.5; Schedule D ss. 1–29 | Open PDF (45 pages, modified 2026-03-23), 2026-11-11 (C2) |
| SRC-45 | Freedom of Information and Protection of Privacy Act, RSBC 1996, c. 165, Part 3 — https://www.bclaws.gov.bc.ca/civix/document/id/complete/statreg/96165_03 | ss. 30.5, 33.1, 36.3 | Open 2026-11-11 (C2), current to November 3, 2026 |
| SRC-31 | ICBC, overview of 2026-04-01 Recovery Network program guide updates — https://www.partners.icbc.com/assets/5KTXnBJHKHgQfFfuIfqlgp/Overview-of-Program-Guide-changes-4-2026.pdf | What changed in April 2026; section 6.1 shown without an amendment to the 45-day sentence | Open PDF, 17 pages, text extracted; opened in fix round 1 |

Not opened (no claim in this repository rests on them as fact): ICBC chiropractic, massage therapy, kinesiology and hand therapy program guides; ICBC physiotherapy guide editions before 2026-09-27; ICBC Health Care Services Terms (C2: PDF returns 404; replaced by the Direct Billing Terms, SRC-43); WorkSafeBC Physiotherapy Services Memorandum of Agreement and its schedules (C1: named by SRC-19, not opened; C2: the Physiotherapy Services Agreement and Schedule D opened, SRC-44; its fee Schedule B not re-read), the fee schedule SRC-20 (not re-opened in C1) and the chiropractic fee schedule; Statistics Canada table 33-10-1175 (locations without employees); PABC and College directories; AWS and email-finder price pages; CRTC Unsolicited Telecommunications Rules and the National DNCL (C2). C2: OIPC guidance (SRC-37 to SRC-40) and the College's standards (SRC-42) are now opened.

Assumptions preserved from the chat and still unresolved: every input in 9.1; every funnel rate; the modelled benefit (2%, CAD 85, half recovered); "two minutes a week" for exports; 120 build hours; "PIPA: low risk if only billing fields are stored in Canada".

## 16. Open decisions for the owner

Points where a correction touches a chat figure or the stop rule. Nothing below has been changed silently; each needs the owner's answer.

| ID | Raised | Inconsistency | `[P]` proposal |
|---|---|---|---|
| OD-1 | C1, 2026-11-11 | The stop rule's first figure (11.3) is called "permanent loss" but includes ICBC visits past PR-01, which ICBC "may" still pay at its discretion `[S: SRC-12]` §6.1. (M-02 in PRD.md was reworded in C1 to report the lines separately.) | Rename it "Past-deadline and ineligible ICBC amounts per month"; keep its arithmetic and threshold; report the *confirmed unpaid* part on its own line in the T-0.4.3 memo. Alternative: gate on PR-03 plus confirmed unpaid only, which needs portal checks during each audit. |
| OD-2 | C1, 2026-11-11 | The base-case pool of 600 reachable clinics `[A]` is not derived from any count; the first primary counts (1,088 BC employer locations in NAICS 621340, 475 with 5–49 employees; 5,621 Full-class physical therapists) cover more professions or count people `[S: SRC-32]` `[S: SRC-33]`. | Keep 600 as the labelled assumption until T-0.1.4 counts Jane-using physiotherapy clinics; if the count is under 1,222, report before any build (section 10). |
| OD-3 | C1, 2026-11-11 | The exact PR-01 lateness and PR-08 limit need the original submission date and the first rejection date, which are not among the 16 fields. | Ask Jane (T-0.1.2) whether either is exportable; if so, add them as fields 17–18 with the owner's written approval (AGENTS.md: a new field needs it); until then the product shows bounds and asks for a portal check. |
| OD-4 | C1, 2026-11-11 | The free audit and the weekly import now use one definition of the exports, with a 365-day Sales date range `[P]`; fully paid lines older than 90 days are then uploaded although the audit does not use them. | Accept for Phase 0; in the application, drop fully paid lines older than 90 days in the browser before upload (a minimiser change, not built in C1). |
| OD-5 | C2, 2026-11-11 | The repository assumed a lawyer would clear sending 16 minimised fields per visit to ClaimCheck. ICBC's Direct Billing Terms Schedule B s. 8(h) (SRC-43) and WorkSafeBC's agreement s. 9.4 and Schedule D (SRC-44) make that depend on each payer's written approval; the College standard asks for consent (SRC-42) | **Model L:** the check runs on the clinic's computer (Phase 0: the preparation workbook with the T-0.1.1 rule formulas); only the clinic-level summary of [compliance/self-check.md](compliance/self-check.md) section 9.2 leaves, through a Canada-hosted channel. The 16-field flow of section 6 (Model R) is used with real rows only after self-check section 9.4. Alternative: keep Model R and send the payer letters (self-check 10.5) before the first audit |
| OD-6 | C2, 2026-11-11 | The Phase 0 cash plan (sections 9.3, 9.6, 12) includes "legal review of the data agreement 1,500 `[A]`", but no lawyer is engaged | Keep the 1,500 as a compliance contingency for the triggers of self-check section 12 (cap unchanged), or remove it and re-run the cash arithmetic; not changed in C2 |
| OD-7 | C2, 2026-11-11 | Section 12 plans an email finder for owners' addresses; CASL s. 10(9)(b) (SRC-34) implies consent only for an address the clinic itself published | Use the finder only to locate published addresses; record the URL and date per address; otherwise walk in, phone, or use the clinic's published inbox. Funnel rates may fall; re-check after the first 250 contacts |

### Owner decisions recorded

| Date | Decision | Effect |
|---|---|---|
| 2026-11-11 | No lawyer is hired for now; legal questions are answered by the owner's own research of primary sources, written per product; the owner accepts the remaining risk (`_coordination/C2-GUIDE.md`) | Lawyer gates (T-0.1.3, O-5, section 14 row 4, schema s. 35(1) note) now read "answered by [compliance/self-check.md](compliance/self-check.md) section X, owner sign-off recorded"; the original question text is kept beside each. Not legal advice. OD-5 to OD-7 stay open |
