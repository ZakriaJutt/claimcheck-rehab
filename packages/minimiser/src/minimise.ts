/**
 * The browser minimiser (T-3.1.1; AD-01; MH-01, MH-02). Raw Jane files never leave this function:
 * its output holds only the 16 allow-listed fields and two ordinals. The claim number is replaced by
 * HMAC-SHA-256 under the clinic key (truncated to 128 bits); the practitioner is replaced by a
 * discipline; the location is used only to filter rows; every other column is dropped and reported.
 * A missing required column blocks the import and names the column; nobody is asked to type a value.
 */
import { parseCsv } from "./csv.js";
import type {
  ClaimRow,
  ColumnReport,
  Discipline,
  ExportProfile,
  MinimisedImport,
  Payer,
  PolicyStatus,
  ReportProfile,
  State,
  Treatment,
  VisitRow,
} from "./types.js";

export class MissingColumnsError extends Error {
  constructor(public readonly report: string, public readonly columns: string[]) {
    super(`The ${report} export is missing required column(s): ${columns.join(", ")}`);
  }
}

/** Shown only on the clinic's screen; the names never leave the browser. */
export class UnmappedPractitionerError extends Error {
  constructor(public readonly practitioners: string[]) {
    super(`Choose a discipline for ${practitioners.length} staff member(s) before importing`);
  }
}

export interface MinimiseOptions {
  profile: ExportProfile;
  key: CryptoKey;
  location: string;
  practitioners: Record<string, Discipline>;
}

const TREATMENT: Record<string, Treatment> = {
  invoice_ref: "kept", date_of_service: "kept", billing_code: "mapped", amount_invoiced: "kept",
  amount_paid: "kept", submission_state: "mapped", state_date: "kept", payer: "mapped",
  practitioner: "replaced", claim_number: "tokenised", location: "used_to_filter",
  policy_status: "mapped", end_date: "kept", treatments_count: "kept", policy_max: "kept",
  next_appointment_date: "kept", date_of_event: "kept",
};

const enc = new TextEncoder();

export async function keyFromRecovery(recovery: string): Promise<CryptoKey> {
  if (!/^[A-Z2-7]{32}$/.test(recovery)) throw new Error("recovery string must be 32 base32 characters");
  return crypto.subtle.importKey("raw", enc.encode(recovery), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
}

export function newRecoveryString(): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return Array.from(bytes, (b) => alphabet[b % 32]).join("");
}

function hex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function claimToken(key: CryptoKey, claimNumber: string): Promise<string> {
  const normalised = claimNumber.trim().toUpperCase().replace(/\s+/g, "");
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(normalised));
  return hex(mac).slice(0, 32);
}

function isoDate(raw: string | undefined): string | null {
  const v = (raw ?? "").trim();
  const m = /^(\d{4})[-/](\d{2})[-/](\d{2})$/.exec(v);
  if (!m) return null;
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
  if (d.getUTCMonth() !== Number(m[2]) - 1) return null;
  return `${m[1]}-${m[2]}-${m[3]}`;
}

function amount(raw: string | undefined): string | null {
  const v = (raw ?? "").trim().replace(/^\$/, "").replace(/,/g, "");
  if (!/^\d{1,4}(\.\d{1,2})?$/.test(v)) return null;
  const [whole, frac = ""] = v.split(".");
  return `${whole}.${frac.padEnd(2, "0")}`;
}

function int(raw: string | undefined): number | null {
  const v = (raw ?? "").trim();
  return /^\d{1,4}$/.test(v) ? Number(v) : null;
}

interface Table {
  get: (row: string[], field: string) => string | undefined;
  rows: string[][];
  columns: ColumnReport[];
  has: (field: string) => boolean;
}

function table(report: "sales" | "policies", csv: string, rp: ReportProfile): Table {
  const [header = [], ...rows] = parseCsv(csv);
  const trimmed = header.map((h) => h.trim());
  const missing = rp.required.filter((r) => !trimmed.includes(r));
  if (missing.length) throw new MissingColumnsError(report, missing);
  const index = new Map<string, number>();
  const columns: ColumnReport[] = trimmed.map((h, i) => {
    const field = rp.columns[h];
    if (field !== undefined) index.set(field, i);
    return { report, header: h, treatment: field !== undefined ? (TREATMENT[field] ?? "dropped") : "dropped" };
  });
  return {
    rows,
    columns,
    has: (f) => index.has(f),
    get: (row, f) => {
      const i = index.get(f);
      return i === undefined ? undefined : row[i];
    },
  };
}

function lookup<T extends string>(map: Record<string, string>, raw: string | undefined, fallback: T): T {
  const v = map[(raw ?? "").trim()];
  return (v ?? fallback) as T;
}

export async function minimise(salesCsv: string, policiesCsv: string, opts: MinimiseOptions): Promise<MinimisedImport> {
  const { profile, key } = opts;
  const sales = table("sales", salesCsv, profile.sales);
  const policies = table("policies", policiesCsv, profile.policies);
  const counts = { unrecognisedStates: 0, unmappedCodes: 0, otherLocationRows: 0, otherPayerRows: 0 };

  const unmapped = new Set<string>();
  for (const row of sales.rows) {
    if ((sales.get(row, "location") ?? "").trim() !== opts.location) continue;
    const who = (sales.get(row, "practitioner") ?? "").trim();
    if (!(who in opts.practitioners)) unmapped.add(who);
  }
  if (unmapped.size) throw new UnmappedPractitionerError([...unmapped].sort());

  const visits: VisitRow[] = [];
  const lineCounter = new Map<string, number>();
  for (const row of sales.rows) {
    if ((sales.get(row, "location") ?? "").trim() !== opts.location) {
      counts.otherLocationRows++;
      continue;
    }
    const invoice = (sales.get(row, "invoice_ref") ?? "").trim() || null;
    const line = (lineCounter.get(invoice ?? "") ?? 0) + 1;
    lineCounter.set(invoice ?? "", line);
    const payer = lookup<Payer>(profile.payer_map, sales.get(row, "payer"), "OTHER");
    if (payer === "OTHER") counts.otherPayerRows++;
    const state = lookup<State>(profile.state_map, sales.get(row, "submission_state"), "unknown");
    if (state === "unknown") counts.unrecognisedStates++;
    const code = lookup(profile.billing_codes, sales.get(row, "billing_code"), "UNMAPPED");
    if (code === "UNMAPPED") counts.unmappedCodes++;
    const claimNo = (sales.get(row, "claim_number") ?? "").trim();
    visits.push({
      row_no: visits.length + 1,
      line_no: line,
      invoice_ref: invoice,
      date_of_service: isoDate(sales.get(row, "date_of_service")),
      payer,
      billing_code: code,
      amount_invoiced: amount(sales.get(row, "amount_invoiced")),
      amount_paid: amount(sales.get(row, "amount_paid")),
      submission_state: state,
      state_date: isoDate(sales.get(row, "state_date")),
      discipline: opts.practitioners[(sales.get(row, "practitioner") ?? "").trim()] ?? "other",
      claim_token: claimNo ? await claimToken(key, claimNo) : null,
    });
  }

  const claims: ClaimRow[] = [];
  const seen = new Set<string>();
  for (const row of policies.rows) {
    if (policies.has("location") && (policies.get(row, "location") ?? "").trim() !== opts.location) {
      counts.otherLocationRows++;
      continue;
    }
    const claimNo = (policies.get(row, "claim_number") ?? "").trim();
    if (!claimNo) continue;
    const payer = lookup<Payer>(profile.payer_map, policies.get(row, "payer"), "OTHER");
    const tok = await claimToken(key, claimNo);
    if (seen.has(`${tok}:${payer}`)) continue;
    seen.add(`${tok}:${payer}`);
    const status = (policies.get(row, "policy_status") ?? "").trim();
    claims.push({
      row_no: claims.length + 1,
      claim_token: tok,
      payer,
      policy_status: status ? lookup<PolicyStatus>(profile.policy_status_map, status, "other") : null,
      end_date: isoDate(policies.get(row, "end_date")),
      treatments_count: int(policies.get(row, "treatments_count")),
      policy_max: int(policies.get(row, "policy_max")),
      next_appointment_date: isoDate(policies.get(row, "next_appointment_date")),
      date_of_event: isoDate(policies.get(row, "date_of_event")),
    });
  }
  return { visits, claims, columns: [...sales.columns, ...policies.columns], counts };
}

/** Idempotency key for POST /imports: SHA-256 of the minimised content (TRD "Import handling"). */
export async function contentHash(m: MinimisedImport, exportDate: string): Promise<string> {
  const body = JSON.stringify({ export_date: exportDate, visits: m.visits, claims: m.claims });
  return hex(await crypto.subtle.digest("SHA-256", enc.encode(body)));
}

/** Request bodies for POST /imports/{id}/rows, at most `size` rows each. */
export function rowRequests(m: MinimisedImport, size = 500): Array<{ visits?: VisitRow[]; claims?: ClaimRow[] }> {
  const out: Array<{ visits?: VisitRow[]; claims?: ClaimRow[] }> = [];
  for (let i = 0; i < m.visits.length; i += size) out.push({ visits: m.visits.slice(i, i + size) });
  for (let i = 0; i < m.claims.length; i += size) out.push({ claims: m.claims.slice(i, i + size) });
  return out;
}
