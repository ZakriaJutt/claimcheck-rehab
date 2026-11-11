/** The minimised payload: exactly the 16 fields of schema.md section 2 plus row_no and line_no. */
export type Payer = "ICBC" | "WSBC" | "OTHER" | "UNKNOWN";
export type State = "unsubmitted" | "submitted" | "rejected" | "partly_paid" | "paid" | "unknown";
export type Discipline = "physiotherapy" | "support" | "other";
export type PolicyStatus = "open" | "closed" | "other";

export interface VisitRow {
  row_no: number;
  line_no: number;
  invoice_ref: string | null;
  date_of_service: string | null;
  payer: Payer;
  billing_code: string;
  amount_invoiced: string | null;
  amount_paid: string | null;
  submission_state: State;
  state_date: string | null;
  discipline: Discipline;
  claim_token: string | null;
}

export interface ClaimRow {
  row_no: number;
  claim_token: string;
  payer: Payer;
  policy_status: PolicyStatus | null;
  end_date: string | null;
  treatments_count: number | null;
  policy_max: number | null;
  next_appointment_date: string | null;
  date_of_event: string | null;
}

export interface ReportProfile {
  version: number;
  columns: Record<string, string>;
  required: string[];
}

export interface ExportProfile {
  sales: ReportProfile;
  policies: ReportProfile;
  payer_map: Record<string, string>;
  state_map: Record<string, string>;
  policy_status_map: Record<string, string>;
  billing_codes: Record<string, string>;
}

export type Treatment = "kept" | "mapped" | "replaced" | "tokenised" | "used_to_filter" | "dropped";

export interface ColumnReport {
  report: "sales" | "policies";
  header: string;
  treatment: Treatment;
}

export interface MinimisedImport {
  visits: VisitRow[];
  claims: ClaimRow[];
  columns: ColumnReport[];
  counts: {
    unrecognisedStates: number;
    unmappedCodes: number;
    otherLocationRows: number;
    otherPayerRows: number;
    unknownPayerRows: number;
  };
}
