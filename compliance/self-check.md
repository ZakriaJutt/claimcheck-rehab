# Compliance self-check — ClaimCheck Rehab

> **Not legal advice.** This is the owner's own reading of primary sources, written on 2026-11-11 under the owner's decision of the same day that no lawyer is hired for now (`_coordination/C2-GUIDE.md`). It replaces "a lawyer must answer first" gates with written answers. The owner accepts the remaining risk. Where a source could not be opened it says so. Section 12 lists the events that mean "get professional help anyway".

Every source below was opened on **2026-11-11** unless marked otherwise; source IDs are those of [Decision.md section 15](../Decision.md#15-sources-and-assumptions). Quotes are short (under 15 words); the rest is paraphrase. `[P]` marks a proposal that needs the owner's decision; nothing here changes the product by itself.

## 0. Answers at a glance

| # | Legal question raised by the documents | Short answer | Residual risk | Section |
|---|---|---|---|---|
| LQ-1 | CASL: may we email clinic owners cold? What must every email contain? | Only to an address the clinic itself published, relevant to its business; every message names the sender, gives a mailing address and contact, and an unsubscribe that works within 10 business days. System emails now carry the identification (code change, tested) | **Low** if the rules are followed; **medium** if an email-finder address is used | 1 |
| LQ-2 | PIPA: may the clinic give us billing rows without asking each patient (s. 18(2))? Who is responsible? | Probably yes for a contractor working only for the clinic's billing purpose, but the clinic stays responsible (s. 4(2)) and the College standard wants consent or law. Under the no-lawyer model nothing row-level leaves, so the question does not arise | Model L: **low**; Model R: **medium** | 2 |
| LQ-3 | PIPA: safeguards (s. 34), retention (s. 35), breach notification | s. 34 "reasonable security"; s. 35(2) destroy when no longer needed; s. 35(1) one-year rule does not apply to us (no decision about a patient). PIPA has **no** mandatory breach notification; OIPC recommends it, and ICBC (72 h) and WorkSafeBC ("immediately") require it by contract | Model L: **low**; Model R: **medium** | 3 |
| LQ-4 | Are minimised rows (no names, DOB, PHN; claim numbers tokenised) still personal information? | **Yes.** The clinic can re-link them; the Jane invoice number points to the patient. Clinic-level counts and totals with no row, date or code are very likely not personal information, but WorkSafeBC's contract still covers them | Rows: treat as PI (certain); aggregates: **low** | 4 |
| LQ-5 | College of Health and Care Professionals of BC standards | Licensees must disclose personal information "only with consent, unless required by law" and limit it to the minimum; storage services must meet privacy law. Model L keeps the clinic inside this | Model L: **low**; Model R: **medium** | 5 |
| LQ-6 | ICBC terms: may claim information go to a contractor? | ICBC's Direct Billing Terms put clinic records about ICBC claims under FIPPA; sending them over the Internet needs ICBC's prior approval or must be contemplated by the Agreement; disclosure of ICBC Confidential Information to third parties needs ICBC's written consent | Model R without ICBC's written approval: **high**; Model L: **low** | 6 |
| LQ-7 | WorkSafeBC agreement: may claim information go to a contractor? | Canada-only storage (including email and backup servers), encryption, no AI training, and no disclosure to third parties without WorkSafeBC's written consent unless necessary to perform the agreement; Schedule D also covers aggregated and de-identified data | Model R without WorkSafeBC's written consent: **high**; Model L: **low to medium** (aggregates) | 7 |
| LQ-8 | Data residency (Canada hosting) | PIPA has no residency rule, but WorkSafeBC's contract requires Canada and ICBC's applies FIPPA; host everything in AWS ca-central-1, no PI in email | **Low** (Canada); foreign-demand exposure through a US-owned cloud: **medium**, contractually handled | 8 |

**Proposed no-lawyer operating model (`[P]`, open decision OD-5):** *Model L — the clinic runs the check on its own computer; only a clinic-level summary of counts and dollar totals leaves (exact list in section 9.2).* The current application design, where 16 minimised fields per visit reach our server (*Model R*), stays a development target with synthetic data and is used with real rows only after the written payer approvals in section 9.4.

---

## 1. CASL — emails to clinic owners, and the product's own emails (LQ-1)

**Sources:** SRC-34 (CASL, S.C. 2010, c. 23, current to 2026-10-19), SRC-35 (CRTC Electronic Commerce Protection Regulations, SOR/2012-36), SRC-36 (Electronic Commerce Protection Regulations, SOR/2013-221). The CRTC's CASL FAQ page (https://crtc.gc.ca/eng/com500/faq500.htm) **could not be opened** (HTTP 403); nothing here rests on it.

**The rule in plain English.**

- s. 6(1): no commercial electronic message (CEM) unless the recipient has consented, expressly or impliedly — CEM only if "the person to whom the message is sent has consented to receiving it". The outreach email offers a free audit leading to a paid pilot: it is a CEM.
- s. 10(9)(b): consent is implied when the person "has conspicuously published" the address, without a no-spam statement, and the message is "relevant to the person's business, role, functions or duties". A clinic's front-desk or owner address printed on its own website or directory listing fits; an address guessed or sold by an email-finder tool does not, because the clinic did not publish it.
- s. 10(9)(a) and 10(10): an existing business relationship (purchase within two years, written contract, inquiry within six months) also implies consent. A clinic that asked about the audit has one for six months.
- SOR/2013-221 s. 3(a)(ii): the business-to-business exclusion applies only "if the organizations have a relationship" — it does not cover cold outreach. s. 4(1): one first message after a referral is excluded if it names the person who referred.
- s. 6(2) and SOR/2012-36 s. 2(1): every CEM names the sender and gives "the mailing address, and either a telephone number providing access to an agent", an email address or a web address; s. 6(3): valid for 60 days. s. 6(2)(c) and s. 11: an unsubscribe that costs nothing, by the same means, given effect "no later than 10 business days after the indication has been sent".
- s. 6(6): messages that confirm a transaction or give factual information about an ongoing subscription need no consent, but s. 6(2) (identification and unsubscribe) still applies to them.
- s. 13: whoever relies on consent "has the onus of proving it". s. 20(4): penalties up to $1,000,000 for an individual and $10,000,000 for any other person.
- s. 6(8)(a): a live two-way phone call is not a CEM. Walk-in visits are outside CASL. The National Do Not Call List rules for phone outreach were **not opened** (see section 12).
- PIPA (SRC-25) s. 1: "contact information" (business name, title, business email, phone) is excluded from personal information, so the prospect list of business contacts is not regulated by PIPA; CASL still is.

**What the business must do.**

1. Build the prospect list (T-0.1.4) with a "source of address" column: the URL where the clinic published it, and the date seen. No URL, no email.
2. Use an email-finder only to find a published address faster; never send to an address the clinic did not publish (open decision OD-7).
3. Send only messages relevant to the clinic's billing (they are); never to a personal address.
4. Put the footer in section 10.3 on every outreach message, follow-up and system message. Keep the contact address and unsubscribe address working for 60 days after the last message.
5. Keep an unsubscribe register (date, address, how received); remove the address the same day, never later than 10 business days; never email it again.
6. Keep a consent record per address (published URL and date, or the inquiry, or the signed pilot) for at least three years after the last message, because the onus is ours.
7. Referral message: name the referrer in the first sentence and send only one message until the person answers.
8. Product emails (invitation, password reset, the future weekly email): identification footer; the invitation and the weekly email also carry the unsubscribe line. **Implemented in C2:** `claimcheck_core.mail.sender_footer`; settings `MAIL_SENDER_NAME`, `MAIL_POSTAL_ADDRESS`, `MAIL_CONTACT`; staging and production refuse to start without the address and contact; tests `tests/unit/test_c2_compliance.py`.

**Red lines.** No email to an address the clinic did not publish or give us. No purchased lists. No message without the footer. No "re:" or misleading subject line (CASL also amends the Competition Act on false or misleading sender and subject information; not researched further). No email after an unsubscribe. No row data or amounts in any email (product rule AD-08).

**Residual risk: low** with the checklist; **medium** if the email-finder route of Decision.md section 12 is used as written, because implied consent then cannot be shown.

## 2. PIPA — who is responsible, and the authority to share (LQ-2)

**Sources:** SRC-25 (Personal Information Protection Act, SBC 2003, c. 63, "current to November 3, 2026", re-opened 2026-11-11); SRC-38 (OIPC BC, *PIPA and AI scribes: best practices for healthcare organizations in BC*, PDF created 2026-01-27, read for its general PIPA statements on vendors).

**The rule in plain English.**

- s. 1: "personal information" is "information about an identifiable individual"; "organization" includes a person, so a sole proprietor ClaimCheck is an organization.
- s. 4(2): an organization is "responsible for personal information under its control", even when a contractor holds it. OIPC: "An organization cannot avoid its obligations under PIPA by contracting with another organization" (SRC-38 p. 4). The clinic is therefore the responsible organization; ClaimCheck is its service provider and is also an organization with its own duties (ss. 4, 5, 34, 35).
- s. 4(3): each organization designates a person responsible for compliance. s. 5: each must "develop and follow policies and practices" and a complaint process.
- s. 6: no collection, use or disclosure without consent unless the Act authorises it. s. 8(1): consent is implied when the purpose is "obvious to a reasonable person" and the individual gives the information for it — patients give billing details so that the clinic can bill ICBC or WorkSafeBC.
- s. 18(2): the clinic may disclose without fresh consent to another organization if the patient consented to the original collection, and the disclosure is solely for those purposes and to "carry out work on behalf of the first organization". s. 12(2) is the matching rule that lets ClaimCheck collect on that basis; s. 10(2) requires ClaimCheck to give the clinic "sufficient information regarding the purpose of the collection".
- s. 56(2): offences (e.g. obstructing the commissioner, deception) carry fines up to $100 000 for an organization; s. 57: damages after a final order.

**Reading.** Helping the clinic get paid on its own invoices is the clinic's billing purpose, so s. 18(2) is a reasonable basis for Model R. It is not certain: s. 18(2)(b)(i) says "solely for the purposes", and the College standard (section 5) asks licensees to disclose only with consent or as required by law. Model L avoids relying on s. 18(2) for patient rows at all.

**What the business must do.**

1. Name a privacy officer for ClaimCheck (the founder) in the data agreement and on the website (s. 4(3)).
2. Write a one-page privacy policy and complaint process (s. 5) and hand it to every clinic before any data moves (s. 10(2)).
3. Use the data agreement in section 10.1; it fixes the purpose, the fields, Canada, security, breach notice, retention and deletion.
4. Ask each clinic to add the notice in section 10.2 to its patient privacy notice and intake form (supports s. 8 and the College standard).
5. Use clinic data only for that clinic's list and audit (Decision.md section 6, "What the founder may not do").

**Red lines.** No use of clinic data for our own purposes (analytics, benchmarks, marketing, training any model). No disclosure to anyone except the sub-processors named in the agreement. No case study with clinic figures unless the clinic agrees in writing, with no patient-level detail.

**Residual risk:** Model L **low** (only clinic-level totals leave; section 4); Model R **medium**.

## 3. PIPA — safeguards, retention, breach response (LQ-3)

**Sources:** SRC-25 ss. 34, 35; SRC-37 (OIPC BC, *Privacy breach quick reference guide for small and medium-sized businesses*, PDF created 2026-04-20); SRC-39 (OIPC BC, *Privacy breaches: tools and resources for the private sector*, PDF created 2026-03-17); SRC-40 (OIPC BC, *BC Physician Privacy Toolkit*, 3rd ed., August 2017 — written for physicians, used here by analogy).

**The rule in plain English.**

- s. 34: protect personal information by "making reasonable security arrangements to prevent unauthorized access", collection, use, disclosure, copying, modification or disposal.
- s. 35(1): if information is used "to make a decision that directly affects the individual", keep it "at least one year after using it". ClaimCheck makes no decision about a patient (it lists invoices for staff), so s. 35(1) does not apply to our copy; the clinic's own records stay in Jane under the College's 16-year rule (section 5). This answers the open point in [schema.md section 9](../schema.md#9-sensitivity-and-retention).
- s. 35(2): destroy, or "remove the means by which the personal information can be associated with particular individuals", once the purpose is served and no legal or business reason remains. The retention periods of Decision.md section 6 (30 days after an audit report, term plus 30 days, backups 35 days, Phase 0 bucket 7 days) satisfy this.
- **Breach notification:** the PIPA text current to 2026-11-03 has no breach-notification section (sections 1–60 read). OIPC: PIPA "does not currently include an explicit requirement" to report (SRC-40); it recommends four steps — "There are four steps to responding to a privacy breach" (SRC-37): contain, assess risk, notify and report where there is a significant risk of harm, prevent. SRC-39's model timeline: decide on reporting to the commissioner generally within 2 days of discovery. The payer contracts are stricter (sections 6 and 7).

**What the business must do.**

1. Security baseline for any device or service that holds clinic data: full-disk encryption; unique accounts with strong passwords and two-factor sign-in; operating system, browser and antivirus up to date; encryption in transit and at rest; access logs kept 24 months (ICBC Schedule B s. 8(c)).
2. Keep the incident register and the deletion register of the Phase 0 procedure.
3. Breach plan (one page, kept with the registers): same day — contain, preserve evidence, tell the clinic owner; within 24 hours — written note to the clinic with what, when, how many rows, which fields (the clinic must tell ICBC within 72 hours and WorkSafeBC immediately); within 2 days — clinic and ClaimCheck decide, with the OIPC tool, whether to notify patients and report to the OIPC; never contact patients or payers ourselves without the clinic's agreement (ICBC Schedule B s. 10(f); WorkSafeBC Schedule D s. 24).
4. Delete on schedule and send the confirmation in section 10.4.

**Red lines.** No clinic data on a personal cloud drive, shared document, chat app, AI tool or email. No copy kept "just in case" after the deletion date. No silent breach.

**Residual risk:** Model L **low** (no rows held); Model R **medium** (one person holds infrastructure credentials, O-12).

## 4. Are minimised billing rows still personal information? (LQ-4)

**Sources:** SRC-25 s. 1 and s. 35(2); SRC-41 (Office of the Privacy Commissioner of Canada, *Interpretation Bulletin: Personal Information*, modified 2013-10-11, citing *Gordon v. Canada (Health)*, 2008 FC 258 — a **federal** test, persuasive only for BC); SRC-44 Schedule D s. 12; SRC-38 p. 15.

**The rule in plain English.** PIPA covers "information about an identifiable individual". The Federal Court test, used by the federal commissioner, asks whether there is a "serious possibility that an individual could be identified" from the information alone or combined with other available information. No BC order squarely on de-identified billing data was found (secondary search only). PIPA s. 35(2) itself treats removing "the means by which" information can be associated with individuals as the alternative to destruction, which implies that data whose means of re-linking still exist is still personal information.

**Answer for ClaimCheck.**

- **The 16-field rows are personal information.** The Jane invoice number is in clear and lets anyone with Jane access find the patient; the clinic holds the token key (application) or the code table (Phase 0); dates of service, crash or injury date, treatment counts and amounts are quasi-identifiers. Removing names, birth date and PHN and tokenising claim numbers reduces harm; it does not take the rows outside PIPA. This confirms the repository's existing position (CLAUDE.md, Decision.md section 6).
- **Clinic-level aggregates** (the summary in section 9.2: counts and dollar totals per payer and class, no row, no date, no code, no invoice number) are very likely not about an identifiable patient: ClaimCheck holds nothing to combine them with. They remain the clinic's business information, and WorkSafeBC's Schedule D s. 12 still applies its terms to data "including if aggregated and de-identified" (section 7).
- OIPC's vendor questions ask what happens to "derived 'de-identified' information" (SRC-38 p. 15): the data agreement answers that it is used only for the clinic and deleted with the rest.

**Red lines.** Never call the rows "anonymous" or "de-identified" in a message, agreement or report; say "minimised billing rows (still personal information)". Never add a free-text field, a date to the summary, or a per-visit amount to the summary.

**Residual risk:** rows — treat as personal information (no doubt); aggregates — **low**.

## 5. College of Health and Care Professionals of BC (LQ-5)

**Sources:** SRC-42 (CHCPBC, *Ethics and Practice Standards*, "Effective April 1, 2026": Privacy and Confidentiality, pp. 32–33; Records, pp. 41–43). The physical-therapy-only 2024 standards found by search appear superseded by this document; not relied on.

**The rule in plain English.** The standards bind the clinic's licensed physiotherapists, not ClaimCheck. Privacy and Confidentiality: 2.1 clearly explain how information is collected, used, stored and disclosed; 2.5 "Disclose personal information only with consent, unless required by law."; 2.6 "Limit disclosure of information to the minimum amount" needed; 3.1 reasonable administrative, technical and physical safeguards; 7.2 report a breach as privacy law requires. Records: 6.1 keep a complete record "for at least 16 years from the date of the last encounter"; 9.1 "Ensure any storage service used complies with all privacy, security", access and retention requirements.

**Reading.** Standard 2.5 is stricter in wording than PIPA s. 18(2): it says "required", not "authorized". A clinic that sends rows to ClaimCheck relying only on s. 18(2) exposes its licensees to a College question. Two fixes: the patient notice and consent line in section 10.2 (consent), or Model L (no disclosure of patient rows). Our copy is not the patient record; the 16-year rule applies to the clinic's Jane records, never to ClaimCheck.

**What the business must do.** 1. Recommend Model L. 2. For any Model R clinic, require the section 10.2 notice to be live before the first export. 3. Never ask a clinic to delete or change its Jane records.

**Red lines.** Never present ClaimCheck as a storage service for patient records. Never ask for chart content, diagnosis or practitioner names (already excluded).

**Residual risk:** Model L **low**; Model R **medium**.

## 6. ICBC — Health Care Direct Billing Terms (LQ-6)

**Source:** SRC-43 (ICBC, *Health Care Direct Billing Terms*, https://www.icbc.com/policies/health-care-direct-billing-terms, "Last updated: November 1, 2025", including Schedule B — Protection of Personal Information). The older *Health Care Services Terms* PDF (https://partners.icbc.com/assets/2fyZ9EPqjOrwslzU1pvLFJ/health-care-service-terms.pdf) returned **HTTP 404**; ICBC material found by search says references to it are being updated to the Direct Billing Terms. ICBC may amend the terms with 21 days' notice (s. 1 area); re-check before each new clinic.

**The rule in plain English.**

- Schedule B s. 4: information the clinic collects in providing services "arising from, connected with, or related to, an ICBC Claim" is **ICBC Personal Information**, and the clinic agrees "to comply with provisions of FIPPA (including Part 3 of FIPPA)" for it. Our billing rows for ICBC visits are exactly that.
- s. 5: use only for performing the Agreement unless ICBC approves in writing; s. 6: access only by the clinic's Representatives who need it — "Representatives" includes "service providers, subcontractors", so a contractor can be one.
- s. 8: security list, including (c) access logs kept "for at least 24 months thereafter", (g) encryption at rest, and (h) no transmission over the Internet unless encrypted **and** "the transmission is approved by ICBC in advance or contemplated under the Agreement".
- s. 10: tell ICBC of a breach "promptly (or in any case within 72 hours)"; (f) tell no third party without ICBC's written consent unless the law compels it.
- s. 12: keep no longer than necessary, then destroy permanently. s. 13: report any foreign demand for disclosure immediately and do not comply with it.
- Body s. 9.2: ICBC Confidential Information (information disclosed by ICBC, which includes claim numbers ICBC issues) goes to third parties only "with the prior written consent of ICBC". s. 9.6 and Schedule B s. 14: breach of Schedule B is grounds for immediate termination of direct billing.

**Reading.** Uploading ICBC visit rows to ClaimCheck's server (Model R) is a transmission over the Internet of ICBC Personal Information. Billing ICBC is part of the Agreement, but a third-party deadline tracker is not named in it; whether it is "contemplated" is uncertain. Without ICBC's written approval the clinic risks its direct-billing status, which is worth far more than CAD 89 a month. Tokenising the claim number keeps ICBC's claim numbers themselves from leaving the clinic (supports s. 9.2), but the invoice number, dates and amounts remain ICBC Personal Information.

**What the business must do.**

1. Model L for ICBC rows: no ICBC row leaves the clinic.
2. Before any Model R use, the clinic (not ClaimCheck) writes to ICBC Health Services asking approval to transmit the 16 minimised fields to its contractor in AWS ca-central-1, encrypted, for invoice-deadline tracking; the written answer is kept on file (template in section 10.5).
3. Flow down Schedule B to ClaimCheck in the data agreement (section 10.1, clause 13): logs 24 months, encryption, 24-hour breach notice to the clinic, foreign-demand notice, destruction.

**Red lines.** No ICBC claim number leaves the clinic in clear. No ICBC row reaches ClaimCheck without ICBC's written approval on file. ClaimCheck never contacts ICBC or an ICBC customer about a breach itself.

**Residual risk:** Model R without approval **high**; with approval **low**; Model L **low**.

## 7. WorkSafeBC — Physiotherapy Services Agreement (LQ-7)

**Source:** SRC-44 (WorkSafeBC, *Physiotherapy Services Agreement*, effective "the 1st day of April, 2026", term to March 31, 2028; PDF created 2026-03-12, modified 2026-03-23, 45 pages, downloaded from https://www.worksafebc.com/resources/health-care-providers/guides/physiotherapy-services-agreement?lang=en&direct=), ss. 2.5, 9.1–9.5 and Schedule D (Privacy Protection Schedule). This closes the "WorkSafeBC agreement not opened" item of Decision.md section 15.

**The rule in plain English.**

- s. 9.1(b): the clinic (the "Contractor") complies with FIPPA and Schedule D; injured-worker records created for WorkSafeBC "must be stored inside Canada only"; email containing personal information must be encrypted.
- s. 9.4: no copying or disclosing Confidential Information (which includes information "relating to Injured Workers, claims") to any third party without WorkSafeBC's prior written consent, "which consent may be arbitrarily withheld", unless necessary to perform the Agreement, required by law, or to auditors, lawyers or insurers.
- s. 2.5: a subcontractor must sign a written agreement carrying all Personnel terms.
- Schedule D: s. 4 annual FIPPA training for staff and permitted subcontractors; s. 10 "encrypted in transit and at rest"; s. 12 the Schedule applies to data "including if aggregated and de-identified"; s. 15 "must not store, access or disclose Personal Information outside Canada", including email, storage, backup and disaster-recovery servers; s. 16 access only where necessary; s. 17 no use of personal information to train or tune any AI model; s. 20 destroy on request, when no longer needed or at the end; s. 22 a privacy management program and breach protocol; s. 24 notify WorkSafeBC's FIPPA Designate immediately of a breach; s. 27 after an unauthorised access, notify the workers and offer credit monitoring "for a minimum of two years" at the contractor's cost (where identity-theft data is involved, s. 28).

**Reading.** WorkSafeBC treats the clinic as its FIPPA service provider. Sending WorkSafeBC rows to ClaimCheck (Model R) is a disclosure of Confidential Information to a third party; "necessary to perform the Agreement" is arguable (the agreement requires invoices within 90 days, s. 6 area), but WorkSafeBC alone decides security reasonableness (Schedule D s. 13). Even Model L's clinic-level totals are covered by Schedule D s. 12; they are used only for the clinic's own service, stay in Canada and are never published.

**What the business must do.**

1. Model L: no WorkSafeBC row leaves the clinic; the summary travels only through a Canada-hosted channel (section 9.3), never ordinary email.
2. Ask WorkSafeBC once, in writing, whether a clinic may share clinic-level counts and dollar totals of its own WorkSafeBC invoices with its software supplier (template in section 10.5). Until answered, the summary may omit the WorkSafeBC lines if the clinic prefers.
3. Before any Model R use: the clinic's written request and WorkSafeBC's written consent on file; data agreement with the Schedule D flow-down (section 10.1): Canada-only including email and backups, encryption, annual training, no AI use, breach notice, destruction, cooperation with reviews.

**Red lines.** No WorkSafeBC data outside Canada in any form, including email providers and backups. No AI tool ever sees it. No Model R for WorkSafeBC rows without WorkSafeBC's written consent.

**Residual risk:** Model R without consent **high**; Model L **low to medium** (the aggregate question in step 2).

## 8. Data residency and foreign access (LQ-8)

**Sources:** SRC-25 (no residency provision in the text read); SRC-38 p. 13 ("PIPA does not contain any specific provisions" on disclosure outside Canada; the s. 34 security assessment must cover it); SRC-40 p. 22 (recommends providers who "store and access personal information within Canada"); SRC-45 (FIPPA, RSBC 1996, c. 165, Part 3, current to November 3, 2026: s. 33.1 a public body may disclose outside Canada "only if the disclosure is in accordance with the regulations"; s. 30.5(2) a service provider's employee must report an unauthorised disclosure immediately); SRC-44 Schedule D s. 15; SRC-43 Schedule B ss. 4, 13.

**Answer.** PIPA alone would allow foreign hosting after a security assessment; the payer contracts do not. Keep every copy of clinic data, including the summary, in Canada: AWS ca-central-1 for database, object store, backups and email (TRD); Phase 0 drive and laptop in Vancouver. Email must not carry personal information at all (AD-08), so a mail provider outside Canada would only see counts and links; keep SES in ca-central-1 anyway. AWS is a US-owned provider, so a foreign demand cannot be ruled out: the agreement makes ClaimCheck tell the clinic at once and refuse to comply voluntarily (ICBC Schedule B s. 13; WorkSafeBC Schedule D s. 19).

**Red lines.** No region other than ca-central-1; no backup or disaster-recovery copy outside Canada; no sub-processor outside Canada for clinic data; no founder access to clinic data from outside Canada (Schedule D s. 15 "access").

**Residual risk: low** for residency; **medium** for foreign-demand exposure, which no contract can remove.

## 9. No-lawyer operating model `[P]` (OD-5)

### 9.1 Model L — the check runs at the clinic

The repository assumed a lawyer would clear sending 16 minimised fields per visit to ClaimCheck. The strongest model that needs no lawyer is that **no row-level data leaves the clinic at all**:

- **Phase 0 (by hand).** The preparation workbook of the [Phase 0 data procedure](../execution-plan.md#phase-0-data-procedure) also carries the rule formulas of T-0.1.1. Clinic staff paste the two Jane exports on the clinic's computer; the workbook produces, on the same computer, the audit page and the weekly list. The founder sits beside staff the first time, never touches the keyboard and never looks at the row sheets (training is done on the synthetic workbook). Only the **Summary** sheet (section 9.2) leaves, through section 9.3. Steps 3 to 7 of the procedure (transfer, check, laptop work, delivery, email incident) then do not apply to rows; steps 1, 2 and 8 stay.
- **Weekly pilot.** Staff repeat the paste each Monday (Decision.md assumes about 10 minutes). ClaimCheck's work is the workbook itself: rule updates as new workbook versions (which contain no clinic data), support by phone or visit, and the monthly summary review with the owner. "Self-serve software instead of a hand-made deliverable per clinic."
- **Application (not built; a design change, not adopted).** The same split in software: an offline page served to the clinic's browser that runs `packages/minimiser` and a TypeScript port of the rule engine, keeps state in a file on the clinic's computer, and sends only the summary. The B2 server build continues with synthetic data only. Adopting this needs a new AD in TRD.md and the owner's decision (OD-5); nothing in the code changes now.
- **Price and gate.** Unchanged: CAD 89 a month; the stop rule (T-0.4.3) is measured from the summaries, which carry every figure the gate uses (Decision.md section 11.3; `measure.audit_figures`).

### 9.2 Exact field list of the Summary (what leaves under Model L)

One summary per clinic per run. Every value is a count or a CAD total rounded to whole dollars, for the whole clinic location. No field holds a date of service, invoice number, claim number or token, billing code, practitioner, policy detail, per-visit amount or free text.

| # | Field | Content |
|---|---|---|
| 1 | `clinic_id` | ClaimCheck's own identifier of the clinic location |
| 2 | `run_date` | Date the exports were taken (the only date in the summary) |
| 3 | `workbook_version`, `rule_catalogue_version` | Which rules produced the figures |
| 4 | `rows_received` | Sales lines pasted |
| 5 | `lookback_in_window`, `lookback_older_open`, `lookback_older_wsbc_correctable`, `lookback_excluded` | The look-back set counts (`measure.LookbackCounts`) |
| 6 | `visits_in_scope`, `visits_rules_not_evaluated`, `visits_could_not_check`, `visits_no_rules_applied` | Check-status counts; they add up to the visits received |
| 7 | `could_not_check_by_reason` | Count per reason code from the closed list in `rules/types.py` (e.g. `unknown_state`, `unmapped_code`) |
| 8 | `items_by_payer_class` | For each payer (ICBC, WSBC, OTHER) × money class (`permanent_certain`, `past_deadline_discretionary`, `confirmed_unpaid`, `delayed_cash`, `admin_time`, `warning`): item count and CAD total — classes on separate lines, never added together |
| 9 | `near_limit_balance` and `near_limit_monthly` for ICBC-01, WSBC-01, WSBC-02 | CAD (`measure.NearLimitMonthly`) |
| 10 | `icbc_cohort_certain`, `icbc_cohort_past_deadline`, `icbc_cohort_confirmed_unpaid` | Balance and monthly CAD (`measure.IcbcCohortMonthly`) |
| 11 | `wsbc_past_deadline`, `wsbc_past_correction`, `wsbc_at_risk` | Balance CAD |
| 12 | `items_marked_done`, `items_confirmed_by_export`, `paid_on_near_limit` | Counts and CAD (M-01) |
| 13 | `staff_minutes` | Minutes staff report for the run |

Rule: if a clinic wants, it may drop the WSBC lines until WorkSafeBC answers section 7 step 2; the summary then says "WSBC lines withheld".

### 9.3 How the summary travels

In person on paper, or typed by the owner into a Canada-hosted form or the Phase 0 upload link (AWS ca-central-1, encrypted, 7-day expiry). Not by ordinary email, chat or shared drive, because WorkSafeBC Schedule D s. 12 and s. 15 reach aggregated data and email servers.

### 9.4 Model R — rows leave (the current application design)

Allowed for a clinic only when all of these are on file: (a) the signed data agreement (section 10.1); (b) the clinic's patient notice (section 10.2) live; (c) ICBC's written approval for ICBC rows (section 6); (d) WorkSafeBC's written consent for WSBC rows (section 7); (e) ClaimCheck's privacy policy, breach protocol and annual training record (WorkSafeBC Schedule D ss. 4, 22); (f) insurance that covers a credit-monitoring obligation the clinic may pass down (Schedule D s. 27–29), or the clinic's written acceptance that it carries it. A clinic may use Model R for one payer and Model L for the other.

## 10. Templates (template — adapt; not legal advice)

### 10.1 Data processing agreement — service-provider clauses

> **Parties.** [Clinic legal name] ("Clinic") and [ClaimCheck legal name] ("Provider").
>
> 1. **Roles.** The Clinic is the organization responsible for the personal information under PIPA s. 4(2). The Provider acts only on the Clinic's behalf and on its written instructions, to help the Clinic track and collect its own ICBC and WorkSafeBC invoices (the "Purpose").
> 2. **Data.** Model L: the Provider receives only the clinic-level Summary listed in Annex A (counts and dollar totals; no patient rows). Model R (only if Annex B approvals are on file): the 16 fields and two ordinals listed in Annex A, minimised on the Clinic's computer. The Provider must refuse and delete anything else it receives, and tell the Clinic the same day.
> 3. **Use.** Only for the Purpose and only for this Clinic. No analytics, benchmarks, marketing, sale, or training or tuning of any AI or machine-learning model, including with de-identified or aggregated data.
> 4. **Location.** All storage, processing, backups, email and access in Canada (AWS ca-central-1 and Vancouver). No access from outside Canada.
> 5. **Security.** Encryption in transit and at rest; unique accounts with two-factor sign-in; least-privilege access; supported and patched systems; access logs kept for the term and 24 months after; annual privacy training of everyone with access.
> 6. **Sub-processors.** Only those listed in Annex C. A new one needs 30 days' written notice and the Clinic's written approval.
> 7. **Breach.** The Provider tells the Clinic's privacy contact within 24 hours of discovering any loss, theft or unauthorised access, use or disclosure, with what is known; contains it; keeps evidence; cooperates; and does not notify patients, payers or the public itself unless the Clinic agrees in writing or the law compels it.
> 8. **Requests and demands.** The Provider forwards any patient access or correction request, and any demand for disclosure (including from outside Canada), to the Clinic at once and does not answer it except as the law compels.
> 9. **Retention and deletion.** Free audit: deleted 30 days after the report unless the Clinic subscribes. Subscription: term plus 30 days. Backups expire after 35 days. On the Clinic's request or at termination: deleted within 7 days, with a written confirmation (Annex D) listing row counts and dates, no row data.
> 10. **Review.** The Clinic, ICBC and WorkSafeBC may review the Provider's compliance on reasonable notice; the Provider gives a written compliance statement on request.
> 11. **Payer terms.** The Provider agrees to comply with ICBC's Health Care Direct Billing Terms, Schedule B, and WorkSafeBC's Physiotherapy Services Agreement, Schedule D, as they apply to the Clinic's service providers and subcontractors, and will sign any flow-down the payers require.
> 12. **Responsibility.** Each party is responsible for its own breach of this agreement. [Liability cap, insurance and indemnity: adapt.]
> 13. **Term and end.** [Term]. Either party may end it with [30] days' notice; the Clinic may end it at once on a breach of clauses 3, 4, 7 or 9.
>
> Annex A: field list (section 9.2 of the self-check; for Model R, schema.md section 2). Annex B: payer approvals on file (dates). Annex C: sub-processors (Amazon Web Services Canada, region ca-central-1: database, storage, email). Annex D: deletion confirmation form.

### 10.2 Clinic notice to patients and intake line

> **Billing and claims (privacy notice addition).** To bill ICBC, WorkSafeBC and other insurers and to make sure we are paid on time, we use service providers who work only on our instructions. [Model L:] Our billing check runs on our own computers; our provider receives only clinic-wide totals, never information about you. [Model R:] Our provider, [name], receives limited billing details for each visit (invoice number, visit date, insurer, fee code, amounts, claim status and a coded claim reference) — never your name, birth date, health number, contact details or clinical notes. It is stored in Canada, used only for our billing, and deleted on a fixed schedule. Questions: [privacy officer, contact].
>
> **Intake form line.** "I understand that [Clinic] uses service providers in Canada to bill my insurer and track payment, as described in the clinic's privacy notice."

### 10.3 Email footer (outreach and product emails)

> --
> Sent by [ClaimCheck legal or business name], [mailing address, BC]. Contact: [email] or [phone].
> You are receiving this because [your clinic publishes this address at <URL> | you asked about the free audit on <date> | you are a ClaimCheck customer].
> To stop receiving messages from us, reply "STOP" or write to [email]; it takes effect within 10 business days.

The product's own emails carry the first and third lines from settings (`MAIL_SENDER_NAME`, `MAIL_POSTAL_ADDRESS`, `MAIL_CONTACT`; `claimcheck_core.mail.sender_footer`).

### 10.4 Deletion confirmation (no row data)

> **Subject: Your ClaimCheck data has been deleted**
> On [date] we deleted all data we held for [clinic name, location] under our agreement of [date]: [n] visit rows, [n] claim rows, [n] items, [n] item events, [n] stored import files [Model L: [n] summaries]. Removed from: [database / object store / encrypted laptop / drive / transfer bucket]. Automated backups that may still contain these rows expire by [date, at most 35 days later] and are not restored except to recover from a failure, after which this deletion is applied again. This letter contains no patient information. Questions: [privacy officer, contact].

### 10.5 Clinic letters to the payers (sent by the clinic, not by ClaimCheck)

> **To ICBC Health Services [or: WorkSafeBC Program Manager, Physiotherapy Services; copy FIPPA Designate].** Our clinic [name, vendor number] would like to use a BC software supplier to track invoice deadlines and unpaid invoices. [Model L:] The software runs on our own computer; only clinic-wide counts and dollar totals would be shared with the supplier, stored in Canada. Please confirm this is acceptable under [the Health Care Direct Billing Terms, Schedule B | the Physiotherapy Services Agreement, s. 9.4 and Schedule D]. [Model R:] We ask your written approval to transmit, encrypted, these 16 minimised fields per visit (listed) to the supplier, hosted in AWS ca-central-1, used only for our billing and deleted on a fixed schedule; the supplier would sign your privacy terms.

### 10.6 Disclaimer on the audit page and weekly list

> This page is produced from your Jane exports by rules taken from ICBC's and WorkSafeBC's published documents (versions listed). It is not legal, billing or payer advice. Items marked "check in portal" must be confirmed in ICBC's or WorkSafeBC's systems. A passed deadline means payment is at the payer's discretion, not that it is lost.

## 11. Red lines (all sections)

1. No email to an address the clinic did not publish or give us; no message without the footer; no email after an unsubscribe.
2. No patient row leaves a clinic under Model L; no ICBC row without ICBC's written approval and no WorkSafeBC row without WorkSafeBC's written consent under Model R.
3. No clinic data outside Canada, in any copy, backup, mailbox or access session.
4. No clinic data in email, chat, shared drives, personal cloud storage or any AI tool; no AI training on it.
5. No use of clinic data for anything but that clinic's list and audit; no cross-clinic figures without written consent.
6. Never call minimised rows anonymous; never write "patient data never leaves" (Model R) — name the fields.
7. No silent breach; no contact with patients or payers about a breach without the clinic.
8. No copy kept past its deletion date.

## 12. When to get professional help anyway

Get a BC privacy lawyer (or at least the OIPC's free guidance line) **before acting** when any of these happens:

1. A complaint from a patient, clinic, payer or the College about our data handling, or any letter from the OIPC, the CRTC, ICBC, WorkSafeBC or the College.
2. A suspected breach involving more than a handful of rows, any ICBC or WorkSafeBC row, or any identifier (name, PHN, birth date).
3. A payer refuses, or attaches conditions to, a section 10.5 request; or a payer's terms change (ICBC's 21-day amendment notice; WorkSafeBC's next agreement after March 2028).
4. A clinic, group or investor asks for a contract term we do not understand, unlimited liability, an indemnity, or insurance we lack.
5. Any foreign or court demand for clinic data.
6. Any move to Model R at scale (more than 3 clinics), a second province, another discipline's college, or any feature that stores files, adds AI or shares data across clinics.
7. Phone outreach at volume: the CRTC Unsolicited Telecommunications Rules and National DNCL were not opened in this check.
8. Selling the business or adding a partner who will see clinic data.

## 13. Sources opened 2026-11-11

| ID | Source | Used for | Access |
|---|---|---|---|
| SRC-25 | PIPA, SBC 2003, c. 63 — https://www.bclaws.gov.bc.ca/civix/document/id/complete/statreg/03063_01 | ss. 1, 3–8, 10, 12, 18, 34, 35, 56, 57 | Open, "current to November 3, 2026"; no breach-notification or residency section |
| SRC-34 | CASL, S.C. 2010, c. 23 — https://laws-lois.justice.gc.ca/eng/acts/E-1.6/FullText.html | ss. 6, 10, 11, 12, 13, 20 | Open, current to 2026-10-19 |
| SRC-35 | CRTC Electronic Commerce Protection Regulations, SOR/2012-36 — https://laws-lois.justice.gc.ca/eng/regulations/SOR-2012-36/FullText.html | ss. 2, 3, 4 | Open, current to 2026-10-19 |
| SRC-36 | Electronic Commerce Protection Regulations, SOR/2013-221 — https://laws-lois.justice.gc.ca/eng/regulations/SOR-2013-221/FullText.html | ss. 3, 4 | Open, current to 2026-10-19 |
| SRC-37 | OIPC BC, Privacy breach quick reference guide for SMEs — https://oipc.bc.ca/documents/guidance-documents/3134 | Four breach steps | Open PDF (created 2026-04-20) |
| SRC-38 | OIPC BC, PIPA and AI scribes: best practices for healthcare organizations in BC — https://www.oipc.bc.ca/documents/guidance-documents/3082 | Vendor responsibility, cross-border, vendor questions | Open PDF (created 2026-01-27); used for general PIPA statements, not for AI |
| SRC-39 | OIPC BC, Privacy breaches: tools and resources for the private sector — https://www.oipc.bc.ca/documents/guidance-documents/1361 | Notification factors, timeline | Open PDF (created 2026-03-17) |
| SRC-40 | OIPC BC, BC Physician Privacy Toolkit, 3rd ed., August 2017 — https://www.oipc.bc.ca/documents/guidance-documents/1400 | Service-contract elements; breach reporting not required by PIPA; Canada storage | Open PDF; written for physicians, used by analogy |
| SRC-41 | OPC Canada, Interpretation Bulletin: Personal Information — https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/pipeda-compliance-help/pipeda-interpretation-bulletins/interpretations_02/ | "Serious possibility" test (*Gordon v. Canada (Health)*, 2008 FC 258) | Open (modified 2013-10-11); federal, persuasive only |
| SRC-42 | CHCPBC, Ethics and Practice Standards, effective 2026-04-01 — https://chcpbc.org/wp-content/uploads/2026/04/Ethics-and-Practice-Standards.pdf | Privacy and Confidentiality 1–7; Records 6, 9 | Open PDF |
| SRC-43 | ICBC, Health Care Direct Billing Terms — https://www.icbc.com/policies/health-care-direct-billing-terms | ss. 9.1–9.6; Schedule B ss. 4–14 | Open, "Last updated: November 1, 2025". Old Health Care Services Terms PDF: HTTP 404 |
| SRC-44 | WorkSafeBC, Physiotherapy Services Agreement (effective 2026-04-01) — https://www.worksafebc.com/resources/health-care-providers/guides/physiotherapy-services-agreement?lang=en&direct= | ss. 2.5, 9.1–9.5; Schedule D ss. 1–29 | Open PDF, 45 pages |
| SRC-45 | FIPPA, RSBC 1996, c. 165, Part 3 — https://www.bclaws.gov.bc.ca/civix/document/id/complete/statreg/96165_03 | ss. 30.5, 33.1, 36.3 | Open, current to November 3, 2026 |
| — | CRTC, CASL FAQ — https://crtc.gc.ca/eng/com500/faq500.htm | — | **Blocked (HTTP 403)**; not relied on |

Not checked: CRTC Unsolicited Telecommunications Rules and the National DNCL (phone outreach); Jane's terms of service (whether a clinic may run third-party tools on its exports — the clinic's own data, not raised by the documents); Competition Act rules on misleading representations beyond the CASL point; OIPC orders on de-identified data (secondary search found none).

## 14. Gates replaced (original question text kept)

| Where | Original gate text | Now |
|---|---|---|
| execution-plan T-0.1.3 | "counsel's note on PIPA s. 18(2), s. 35, ICBC terms, WorkSafeBC agreement and the college standard"; "Counsel's note in hand **before** the first export is accepted" | Answered by sections 2, 3, 5, 6, 7 of this file; owner decision (no lawyer, residual risk accepted) recorded 2026-11-11. First export under Model L after OD-5; under Model R after section 9.4 |
| execution-plan Phase 0 data procedure | "All of it is a proposal `[P]` pending counsel's reading" | Answered by section 9.1 (Model L replaces steps 3–7 for rows) and section 3 |
| Decision.md section 6 | "Lawyer review is task T-0.1.3"; "Task T-0.1.3 closes these before any export is accepted" | Answered by sections 2, 5, 6, 7 and 8 |
| Decision.md section 14, row 4; verification O-5 | "Lawyer's reading of PIPA s. 18(2), the ICBC terms, the WorkSafeBC agreement and the college standard" | Answered by sections 2, 5, 6, 7 |
| schema.md section 9 | "PIPA s. 35(1) … judged not to apply `[A]` … To be confirmed in T-0.1.3" | Answered by section 3: does not apply |

**Owner sign-off:** decision of 2026-11-11 (`_coordination/C2-GUIDE.md`): no lawyer for now; written research replaces the lawyer gates; the owner accepts the remaining risk. The choice of operating model (OD-5) and the outreach change (OD-7) remain open owner decisions in [Decision.md section 16](../Decision.md#16-open-decisions-for-the-owner).
