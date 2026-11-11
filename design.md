# Design brief — ClaimCheck Rehab

Labels and sources: [Decision.md](Decision.md#how-numbers-are-labelled-used-in-all-ten-files). Every dimension, colour and word of microcopy here is an author proposal `[P]`. Screens are S-nn in [App-flow.md](App-flow.md). Example values are synthetic.

## 1. Who is looking, and when

A front-desk lead between patients, on a clinic desktop at 1280–1440 px wide, often interrupted. An owner on a laptop or phone in the evening, reading totals. The interface must answer two questions at a glance: *what do I have to do today* and *how much is at stake*.

Design decisions:

| ID | Decision |
|---|---|
| DD-01 | Days left is the largest thing on a row; money is second |
| DD-02 | The three classes have fixed names, order, icons and colours everywhere; colour is never the only signal |
| DD-03 | Every flag shows its rule in one plain sentence with the payer's own wording one click away |
| DD-04 | "Not checked" (`not_evaluated`) has its own look and is never green |
| DD-05 | Nothing leaves the browser without a review table directly above the button that sends it |
| DD-06 | Marked-done is not done: "Awaiting confirmation" is a distinct state until an export proves it |
| DD-07 | No patient-facing words: the product says "visit" and "Jane invoice", never a name |

## 2. Layout and hierarchy

- App shell: left navigation 220 px (This week, Unpaid, Imports, Pilot report, Rules, Settings); content column max 1120 px; top bar with clinic name, data-freshness chip and account menu.
- Under 900 px the navigation collapses to a top menu; under 640 px tables become stacked cards with the same field order; no horizontal scrolling at 320 px wide except inside the import review table, which scrolls within its own labelled region.
- One primary button per screen, right of secondary actions, never in a different place for the same action.

## 3. Type, colour, components

- **Type:** system UI font stack. 16 px body, 14 px table secondary, 20 px section, 28 px page title; numerals tabular in tables; days-left figure 20 px semi-bold.
- **Colour (text on white unless stated; all text pairs chosen for at least 4.5:1, borders and icons at least 3:1, to be measured in T-5.2.4):** ink `#1F2933`; muted `#52606D`; primary `#0B5CAD`; *Deadline soon* amber `#8A4B00` on `#FFF4E0`; *Lost* red `#9B1C1C` on `#FDECEC`; *Can still be collected* blue `#0B5CAD` on `#E8F1FB`; *Not checked* grey `#3E4C59` on `#EEF1F4` with a dashed border; *Confirmed* green `#1B6E3C` on `#E6F4EA`.
- **Class chips:** icon + word: clock "Deadline soon", arrow-loop "Can still be collected", cross-circle "Lost (payer rule)", question-circle "Past payer deadline – payment at payer's discretion", circle-slash "Confirmed unpaid (payer outcome recorded)" (C1: "Probably lost" withdrawn), gear "Jane set-up", dash "Not checked".
- **Components:** data table with sortable headers (buttons, with sort state exposed), filter bar of native selects, chip, banner (info, warning, error), stepper for S-05 and S-04, dialog for confirmations (focus trapped, Escape closes, focus returns to the trigger), toast only for non-critical confirmation and always mirrored in a live region, skeleton rows while loading.
- **Targets:** every clickable target at least 24 × 24 CSS px; row actions 32 px high.

## 4. Principal screens, in enough detail to sketch

**S-07 This week's list.** Title "This week" with the freshness chip ("Jane export of Mon 9 Nov · checked today") and, beside it, the permanent count line "970 checked · 43 could not be checked · 171 no rules applied". Below it three summary tiles in a row: *Deadline in 14 days or less — 7 visits — $679*; *Can still be collected — 12 — $1,164*; *Lost (payer rule) — 1 — $97*; *Past payer deadline, payer's discretion — 2 — $194* (shown apart, never added to Lost; C1). Then the filter bar. Then grouped tables. Columns: checkbox · Days left (e.g. **6**) with the deadline date beneath · Jane invoice · Payer · Service date · Why (one sentence, e.g. "Not yet invoiced to ICBC") · Amount · Status. A sticky footer appears when rows are selected: "3 selected · Mark as… · Clear".

**S-08 Item detail.** Two columns. Left: header "Jane invoice 10432 · ICBC · Standard Treatment · $97.00"; a timeline bar from the service date to the limit with today marked and "6 days left — submit by Sat 21 Nov (ICBC limit Sun 22 Nov)"; a "Why this is flagged" card with the plain sentence, then "ICBC Physiotherapy program guide, section 6.1, effective 27 Sep 2026" and the rule version; a list "Other checks on this visit" with each result as a chip, including *Not checked — no crash date in the export*. Right: "What did you do?" radio group with the six outcomes, a reason list (shown for "Not an error"; no free text), Save; beneath it the history.

**S-05 Import, step 2.** Heading "Review what will be uploaded. Nothing has been sent yet." A three-group table: *Kept (14)*, *Replaced by a code (2)*, *Removed on this computer (6)* with each Jane column name and, for removed columns, a struck-through lock icon and the words "never leaves this computer". A summary: "1,184 visits: ICBC 702, WorkSafeBC 311, other insurers 171 · service dates 12 Aug – 9 Nov 2026 · 3 rows could not be read". Primary button "Upload 1,184 rows"; secondary "Start again".

**S-10 Pilot report.** Four cards in the order M-01 to M-04, each with the figure, its plain definition, the inputs, and a link to the rows. A fifth card: "Refund test: $291 paid on near-limit items so far · threshold $267 · 11 of 13 exports supplied". A sixth, always shown: "Missed by ClaimCheck: 0".

**S-12 Data.** A plain table "What we hold" (visits 4,712; claims 388; items 164; the 16 billing fields per visit, including Jane invoice numbers; no names, birth dates or health numbers; hosted in Canada), retention dates, then three clearly separated actions with the destructive one last and outlined in red.

## 5. Interaction feedback and microcopy

| Situation | Copy |
|---|---|
| **Pending operation** (import processing, S-06) | "Checking 1,184 visits against ICBC and WorkSafeBC rules. This usually takes under a minute. You can leave this page; the list will be ready when you come back." |
| **Recoverable error** (export shape changed, S-05) | "We couldn't find the column 'Invoice #' in the Sales export. Jane may have changed the export. Nothing was uploaded. You can send us the column headings (no patient data) and we'll fix it, usually within one working day." Buttons: "Send column headings", "Choose a different file". |
| **Human approval** (owner deleting data, S-12) | "Delete all data for Harbourview Physio? This removes 4,712 visits, 388 claims and 164 items. Copies in backups expire within 35 days. Activity records without visit details are kept. This cannot be undone. Enter your password and code to confirm." Button: "Delete all clinic data". |
| Human approval (operator publishing a rule, S-14) | "Publish ICBC-06 version 4? Standard Treatment $97.00 from 1 Apr 2026. 32 of 32 fixtures pass. 5 clinics will be re-checked." |
| Marked done | "Marked as submitted. We'll confirm it when your next Jane export shows the invoice as submitted." |
| Reopened | "You marked this as submitted on 3 Nov. Jane's export of 10 Nov still shows it as unsubmitted, so it's back on your list. 6 days left." |
| Not checked | "Not checked: Jane's export has no crash date for this claim, so we can't tell whether the visit is inside ICBC's first 12 weeks. We checked the policy end date instead." |
| Stale data | "This list is based on the Jane export of 2 Nov (9 days ago). Deadlines are counted to today, but anything invoiced or paid since then isn't shown. Upload a new export." |
| Nothing found (shown only when nothing is unchecked, fix round 1 B1-001) | "Nothing needs action from the 1,013 visits we checked. 0 could not be checked and 171 had no rules applied." When any visit or row could not be checked the sentence is not shown; the "Could not check" copy below is used instead. |
| Could not check | "43 visits could not be checked: Jane's export shows a claim state we don't recognise. They may be at risk. We've been alerted; meanwhile check them in Jane." |
| ICBC marked submitted | "Jane shows this as submitted on 3 Nov, but Jane has no link to ICBC. Check ICBC's portal. If it isn't there, 6 days are left." |
| Past payer deadline (C1) | "Not invoiced within ICBC's 45 days (limit 4 Nov). ICBC may still pay it at its discretion. Submit it now and check the outcome in ICBC's portal; this is not counted as lost." |
| Confirmed unpaid (C1) | "You recorded on 18 Nov that ICBC declined this invoice. Counted as confirmed unpaid. If a payment appears in a later Jane export, it leaves this group." |

Tone: short sentences, the payer named, the date given, no blame, no exclamation marks.

## 6. Inspecting evidence, correcting, and draft versus confirmed

- **Source evidence.** The product holds no documents. Evidence for a flag is (a) the row values as exported from Jane, shown on S-08 with the import date they came from, (b) the state history across imports, and (c) the rule sentence with payer, document, section and effective date. "Find this in Jane" gives the invoice number in a copyable field.
- **Correcting a suggestion.** A flag is a suggestion. Staff correct it with "Not an error" and a reason picked from a fixed list (already paid, payer approved, duplicate row, rule looks wrong, not our claim, other); the item closes, counts against M-07, and can be undone. A wrong rule is reported from the same card ("This rule looks wrong") and reaches the operator with the rule ID only.
- **Draft versus confirmed.** Three visibly different states: *Open* (white row), *Awaiting confirmation* (grey text, hourglass, "marked by Sam on 3 Nov"), *Confirmed by Jane export* (green tick, moved to a collapsed "Done" group). Only *Confirmed* amounts count toward M-01. In S-14, a rule version is *Draft* (dashed outline, not applied to any clinic) until published.

## 7. Responsive behaviour

- 1280 px and up: full tables. 900–1279 px: the Status and Payer columns merge under "Why". Under 640 px: cards; the days-left figure stays top-left; bulk selection remains available through a "Select" mode.
- S-05 file processing happens on the device; on a phone the screen recommends a computer but does not block.

## 8. Accessibility map

WCAG 2.2 `[S: SRC-27]`, levels A and AA. These are **design intentions and planned manual checks**; nothing has been tested and no conformance is claimed.

| Criterion | Where it bites | Planned manual check (task T-5.2.4) |
|---|---|---|
| 1.3.1 Info and Relationships | S-07, S-09 tables; S-05 review table | Headers announced with each cell by a screen reader; groups have headings |
| 1.4.1 Use of Color | Class chips, days-left urgency | Greyscale screenshot still distinguishes every class and state |
| 1.4.3 Contrast (Minimum); 1.4.11 Non-text Contrast | All chips, banners, focus rings, dashed "Not checked" border | Measure each pair in section 3 |
| 1.4.10 Reflow | S-07, S-08 at 320 px | No two-direction scrolling except the labelled import table region |
| 2.1.1 Keyboard; 2.1.2 No Keyboard Trap | S-05 file choice, bulk select, dialogs | Complete an import, resolve an item and delete data without a mouse |
| 2.4.3 Focus Order; 2.4.7 Focus Visible; 2.4.11 Focus Not Obscured (Minimum) | Sticky bulk footer on S-07; dialogs | Focused row is not hidden behind the sticky footer; focus returns to the trigger on close |
| 2.5.7 Dragging Movements | S-05 drag-and-drop | File buttons do everything dragging does |
| 2.5.8 Target Size (Minimum) | Row checkboxes, chips that act as filters | Measure 24 × 24 px minimum |
| 2.2.1 Timing Adjustable | 30-minute idle sign-out; 12-hour absolute limit; 5-minute code step on S-02 | Idle: warning two minutes before, with "Stay signed in". Absolute limit: warning ten minutes before; work restored after sign-in. Code step: time left shown; restarting keeps the email. Whether the 12-hour and 5-minute limits meet the criterion's conditions is **not established** and is checked in T-5.2.4 |
| 3.2.2 On Input | Filter selects on S-07 | Changing a filter updates the list without moving focus or navigating |
| 3.3.1 Error Identification; 3.3.3 Error Suggestion | S-01, S-05 missing column, S-08 missing reason | Error names the field in text; focus moves to the summary; the suggestion is stated |
| 3.3.2 Labels or Instructions | All forms; weekly minutes on S-10 | Visible labels; units stated ("minutes") |
| 3.3.4 Error Prevention (Legal, Financial, Data) | S-05 upload, S-12 delete | Review step before each; outcomes reversible |
| 3.3.7 Redundant Entry | S-04 steps, S-05 retry | Nothing already entered is asked again |
| 3.3.8 Accessible Authentication (Minimum) | S-01, S-02 | Paste and password managers work for password and code |
| 1.3.5 Identify Input Purpose | S-01, S-03 | `autocomplete` set for email, current and new password, one-time code |
| 4.1.2 Name, Role, Value | Chips, sort buttons, stepper | Each has an accessible name and state |
| 4.1.3 Status Messages | Import progress, "Marked as submitted", evaluation running, reopened count | Announced through a polite live region without moving focus |

Known gap, stated as a gap: the in-browser file processing has not been tried with any screen reader, and large tables on a phone have not been tried with screen magnification; both are **not met until tested**.
