export interface Clause {
  id: string;
  clause_ref: string;
  text: string;
  ordinal: number;
}

export interface InstrumentVersion {
  id: string;
  instrument_id: string;
  version_label: string;
  source_url: string | null;
  content_hash: string;
  clauses: Clause[];
}

export interface Instrument {
  id: string;
  title: string;
  jurisdiction: string;
  kind: string;
  citation: string | null;
  recorded_at: string;
}

export interface InstrumentDetail extends Instrument {
  versions: InstrumentVersion[];
}

export interface ExtractedField {
  value: string;
  clause_ref: string;
  confidence: number;
}

export type ObligationFields = Record<"who" | "what" | "when" | "threshold" | "enforcer", ExtractedField>;

export interface Obligation {
  id: string;
  clause_id: string;
  summary: string;
  obligation_type: string;
  fields: ObligationFields;
  confidence: number;
  extracted_by: string;
  approved: boolean;
  approved_by_user_id: string | null;
  approved_at: string | null;
}

export type PredicateStatus = "draft" | "approved";

export interface Predicate {
  id: string;
  obligation_id: string;
  predicate_key: string;
  expression: Record<string, unknown>;
  status: PredicateStatus;
  drafted_by_ai: boolean;
  approved_by_user_id: string | null;
  approved_at: string | null;
}

export interface PredicateTestResult {
  profile_name: string;
  outcome: "binds" | "does_not_bind" | "ambiguous";
  missing_field_keys: string[];
}

export interface CostTemplate {
  id: string;
  obligation_id: string | null;
  name: string;
  drivers: { key: string; label: string }[];
  formula: Record<string, unknown>;
  currency: string;
  source_basis: string;
  maturity_tier: string;
  valid_from: string;
  valid_to: string | null;
}

export interface OnboardingMetric {
  instrument_id: string;
  instrument_title: string;
  onboarding_hours: number;
  started_at: string;
  completed_at: string;
}

export interface MonthlyMetricsReport {
  period_start: string;
  period_end: string;
  time_to_exposure_list_minutes_avg: number | null;
  time_to_approved_memo_minutes_avg: number | null;
  review_minutes_avg: number | null;
  onboarding_hours_avg: number | null;
  override_count: number;
  memos_approved_count: number;
  used_in_ic_count: number;
}
