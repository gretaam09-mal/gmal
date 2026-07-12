export type Outcome = "binds" | "does_not_bind" | "ambiguous";

export interface AnalysisItem {
  id: string;
  predicate_id: string;
  instrument_title: string;
  obligation_summary: string;
  outcome: Outcome;
  missing_field_keys: string[];
  rationale: string;
  clause_refs: string[];
  amount: number | null;
  currency: string;
  impact_band: string;
  confidence: number;
  first_obligation_date: string | null;
  memo_status: string;
  engine_version: string;
  computed_at: string;
}

export interface Analysis {
  id: string;
  workspace_id: string;
  entity_profile_id: string;
  status: string;
  created_at: string;
  items: AnalysisItem[];
}
