/** UT-11 and the MH-02 header checks. Every value is synthetic. */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  MissingColumnsError,
  RaggedRowError,
  UnmappedPractitionerError,
  contentHash,
  keyFromRecovery,
  minimise,
  rowRequests,
} from "../src/index.js";
import type { ExportProfile } from "../src/index.js";

const profile = JSON.parse(
  readFileSync(fileURLToPath(new URL("../../core/claimcheck_core/profiles/jane_v1.json", import.meta.url)), "utf8"),
) as ExportProfile;

const DROPPED = ["Patient Name", "Patient Number", "Date of Birth", "Personal Health Number", "Address",
  "Phone", "Email", "Adjuster Name", "Adjuster Email", "Policy Notes", "Diagnosis Code"];
const SALES_HEADER = ["Invoice #", "Purchase Date", "Payer", "Billing Code", "Amount to Insurer", "Insurer Payment",
  "Claim State", "State Changed", "Staff Member", "Claim #", "Location", ...DROPPED];

const people = [
  ["Zelda Quarrington", "PN-77341", "1979-03-14", "9000000011", "12 Imaginary Way", "604-555-0142",
    "zelda@example.test", "Adjuster Fictional", "adj@example.test", "Note: synthetic", "S83.5"],
  ["Ignatius Vellacourt", "PN-88412", "1990-12-01", "9000000029", "88 Pretend Ave", "604-555-0177",
    "ig@example.test", "Adjuster Madeup", "adj2@example.test", "Note: invented", "M54.2"],
];

function csv(rows: string[][]): string {
  return rows.map((r) => r.map((c) => (/[",\n]/.test(c) ? `"${c.replace(/"/g, '""')}"` : c)).join(",")).join("\r\n");
}

const salesRows = [
  ["INV-1001", "2026-10-01", "ICBC", "PT-ICBC-TX", "$97.00", "0", "Unsubmitted", "", "Pat Physio",
    "CLM-ALPHA-1", "Harbourview Main", ...people[0]!],
  ["INV-1002", "2026-10-08", "ICBC", "PT-ICBC-TX", "97", "", "Sent", "", "Pat Physio",
    "CLM-ALPHA-1", "Harbourview Main", ...people[0]!],
  ["INV-1003", "2026-10-09", "WorkSafeBC", "19102", "95.00", "95.00", "Paid", "2026-10-20", "Kim Kinesiologist",
    "WSB-BETA-2", "Harbourview Main", ...people[1]!],
  ["INV-1003", "2026-10-09", "WorkSafeBC", "19999", "1,200.5", "", "Paid", "", "Kim Kinesiologist",
    "WSB-BETA-2", "Harbourview Main", ...people[1]!],
  ["INV-2001", "2026-10-02", "Pacific Blue Cross", "MT-60", "120.00", "", "Unsubmitted", "", "Pat Physio",
    "EH-GAMMA", "Other Location", ...people[1]!],
];
const SALES = csv([SALES_HEADER, ...salesRows]);
const POLICIES = csv([
  ["Claim #", "Payer", "Status", "End Date", "Number of Treatments", "Policy Maximum", "Next Appointment",
    "Date of Accident/Injury", "Location", "Adjuster Phone", "Internal Policy Name"],
  ["CLM-ALPHA-1", "ICBC", "Active", "2026-12-31", "2", "25", "2026-11-12", "2026-09-28", "Harbourview Main",
    "604-555-0199", "Zelda crash policy"],
  ["WSB-BETA-2", "WorkSafeBC", "Closed", "", "1", "", "", "2026-09-30", "Harbourview Main", "604-555-0198",
    "Ignatius work injury"],
]);

const practitioners = { "Pat Physio": "physiotherapy", "Kim Kinesiologist": "support" } as const;
const KEY1 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
const KEY2 = "MNOPQRSTUVWXYZ234567ABCDEFGHIJKL";

async function run(key = KEY1, sales = SALES, policies = POLICIES) {
  return minimise(sales, policies, { profile, key: await keyFromRecovery(key), location: "Harbourview Main",
    practitioners: { ...practitioners } });
}

describe("UT-11 minimiser", () => {
  it("sends exactly the 16 fields plus two ordinals", async () => {
    expect(SALES_HEADER).toHaveLength(22);
    const out = await run();
    const keys = new Set<string>();
    for (const r of [...out.visits, ...out.claims]) Object.keys(r).forEach((k) => keys.add(k));
    expect([...keys].sort()).toEqual([
      "amount_invoiced", "amount_paid", "billing_code", "claim_token", "date_of_event", "date_of_service",
      "discipline", "end_date", "invoice_ref", "line_no", "next_appointment_date", "payer", "policy_max",
      "policy_status", "row_no", "state_date", "submission_state", "treatments_count",
    ]);
    expect(keys.size).toBe(18);
  });

  it("leaves no dropped, replaced or tokenised value anywhere in the output", async () => {
    const out = await run();
    const wire = JSON.stringify(rowRequests(out)) + (await contentHash(out, "2026-11-09"));
    const secrets = [...people.flat(), "Pat Physio", "Kim Kinesiologist", "Harbourview Main", "Other Location",
      "CLM-ALPHA-1", "WSB-BETA-2", "EH-GAMMA", "604-555-0199", "Zelda crash policy", "Ignatius work injury",
      "Pacific Blue Cross", "INV-2001"];
    for (const s of secrets) expect(wire).not.toContain(s);
  });

  it("tokens repeat within a key and differ between keys", async () => {
    const a = await run(KEY1);
    const b = await run(KEY2);
    expect(a.visits[0]!.claim_token).toMatch(/^[0-9a-f]{32}$/);
    expect(a.visits[0]!.claim_token).toBe(a.visits[1]!.claim_token);
    expect(a.visits[0]!.claim_token).toBe(a.claims[0]!.claim_token);
    expect(a.visits[0]!.claim_token).not.toBe(b.visits[0]!.claim_token);
  });

  it("maps states, codes, payers and amounts; unknown wording becomes unknown and is counted", async () => {
    const out = await run();
    expect(out.visits).toHaveLength(4); // the other location's row is filtered out
    expect(out.counts).toEqual({ unrecognisedStates: 1, unmappedCodes: 1, otherLocationRows: 1, otherPayerRows: 0,
      unknownPayerRows: 0 });
    expect(out.visits[1]!.submission_state).toBe("unknown");
    expect(out.visits[0]).toMatchObject({ billing_code: "ICBC-ST", amount_invoiced: "97.00", payer: "ICBC",
      discipline: "physiotherapy", line_no: 1 });
    expect(out.visits[2]).toMatchObject({ payer: "WSBC", discipline: "support", line_no: 1 });
    expect(out.visits[3]).toMatchObject({ billing_code: "UNMAPPED", line_no: 2, amount_invoiced: "1200.50" });
    expect(out.claims[1]).toMatchObject({ policy_status: "closed", payer: "WSBC", end_date: null });
  });

  it("reports every column as kept, mapped, replaced, tokenised, used to filter or dropped", async () => {
    const out = await run();
    const by = Object.fromEntries(out.columns.filter((c) => c.report === "sales").map((c) => [c.header, c.treatment]));
    expect(by["Claim #"]).toBe("tokenised");
    expect(by["Staff Member"]).toBe("replaced");
    expect(by["Location"]).toBe("used_to_filter");
    for (const d of DROPPED) expect(by[d]).toBe("dropped");
  });
});

describe("MH-02 export shape", () => {
  it("a missing required column blocks the import and names it", async () => {
    const renamed = SALES.replace("Claim State", "Claim Status");
    await expect(run(KEY1, renamed)).rejects.toThrow(MissingColumnsError);
    await expect(run(KEY1, renamed)).rejects.toThrow(/Claim State/);
  });

  it("an unmapped practitioner blocks the import instead of guessing a discipline", async () => {
    const extra = SALES.replace("Kim Kinesiologist", "New Hire");
    await expect(run(KEY1, extra)).rejects.toThrow(UnmappedPractitionerError);
  });

  it("splits rows into requests of at most 500", async () => {
    const out = await run();
    const reqs = rowRequests(out, 3);
    expect(reqs.map((r) => (r.visits ?? r.claims ?? []).length)).toEqual([3, 1, 2]);
  });
});

describe("fix round 1 regressions (reviewer cases M1, M2, M3, M6)", () => {
  const H = ["Patient Name", "Invoice #", "Purchase Date", "Payer", "Billing Code", "Amount to Insurer",
    "Insurer Payment", "Claim State", "State Changed", "Staff Member", "Claim #", "Location"];
  const POL = "Claim #,Payer\r\nCLM-1,ICBC";
  const good = "Zelda Q,INV-1,2026-10-01,ICBC,PT-ICBC-TX,97.00,0,Unsubmitted,,Pat Physio,CLM-1,Harbourview Main";
  const go = async (rows: string[], pol = POL) =>
    minimise([H.join(","), ...rows].join("\r\n"), pol, { profile, key: await keyFromRecovery(KEY1),
      location: "Harbourview Main", practitioners: { "Pat Physio": "physiotherapy" } });

  it("B1-005: a row with one more field than the header blocks the import and names the row", async () => {
    const longer = "Quarrington,Zelda,INV-2,2026-10-01,ICBC,PT-ICBC-TX,97.00,0,Unsubmitted,,Pat Physio,CLM-1," +
      "Harbourview Main";
    const err = await go([good, longer]).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(RaggedRowError);
    expect((err as RaggedRowError).rowNumbers).toEqual([3]);
    expect((err as Error).message).not.toContain("Zelda");
  });

  it("B1-005: a row with fewer fields than the header blocks the import", async () => {
    await expect(go(["Zelda Q,INV-1,2026-10-01,ICBC"])).rejects.toThrow(RaggedRowError);
    await expect(go([good], "Claim #,Payer\r\nCLM-1")).rejects.toThrow(RaggedRowError);
  });

  it("B1-005: Location before the name (reviewer M6) cannot shift a first name into invoice_ref", async () => {
    const h = ["Location", "Staff Member", "Patient Name", "Invoice #", "Purchase Date", "Payer", "Billing Code",
      "Amount to Insurer", "Insurer Payment", "Claim State", "State Changed", "Claim #"];
    const row = "Harbourview Main,Pat Physio,Quarrington,Zelda,INV-1,2026-10-01,ICBC,PT-ICBC-TX,97.00,0,Unsubmitted,,CLM-1";
    await expect(minimise(h.join(",") + "\r\n" + row, POL, { profile, key: await keyFromRecovery(KEY1),
      location: "Harbourview Main", practitioners: { "Pat Physio": "physiotherapy" } })).rejects.toThrow(RaggedRowError);
  });

  it("B1-007: a practitioner named like a prototype member is unmapped, not a function", async () => {
    await expect(go([good.replace("Pat Physio", "constructor")])).rejects.toThrow(UnmappedPractitionerError);
  });

  it("B1-007: unrecognised payer wording is UNKNOWN (could not check), listed insurers are OTHER", async () => {
    const out = await go([good.replace(",ICBC,", ",ICBC Physiotherapy,"),
      good.replace("INV-1", "INV-9").replace(",ICBC,", ",Pacific Blue Cross,")]);
    expect(out.visits.map((v) => v.payer)).toEqual(["UNKNOWN", "OTHER"]);
    expect(out.counts.unknownPayerRows).toBe(1);
  });
});
