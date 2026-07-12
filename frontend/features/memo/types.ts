export type MemoStatus = "draft" | "in_review" | "approved";

export interface PhaseEntry {
  period: string;
  amount: string;
}

export interface MemoObligation {
  predicate_id: string;
  obligation_summary: string;
  clause_refs: string[];
  rationale: string;
  impact_low: string;
  impact_likely: string;
  impact_high: string;
  currency: string;
  phased_schedule: PhaseEntry[];
  present_value: string;
  what_it_requires: string;
  why_it_applies: string;
}

export interface ExcludedObligation {
  predicate_id: string;
  obligation_summary: string;
  outcome: string;
  rationale: string;
}

export interface MemoContent {
  headline: {
    low: string;
    likely: string;
    high: string;
    currency: string;
  };
  confidence_grade: string;
  confidence_score: string;
  obligations: MemoObligation[];
  excluded: ExcludedObligation[];
  headline_summary: string;
  excluded_summary: string;
  change_note?: string;
  superseded_version?: number;
}

export interface Assumption {
  id: string;
  key: string;
  value: Record<string, unknown>;
  source: string;
  note: string | null;
}

export interface MemoVersion {
  id: string;
  memo_id: string;
  version: number;
  status: MemoStatus;
  content: MemoContent;
  confidence_grade: string | null;
  approved_at: string | null;
  approved_by_user_id: string | null;
  created_by_user_id: string;
  created_at: string;
  assumptions: Assumption[];
}

export interface Memo {
  id: string;
  workspace_id: string;
  analysis_id: string | null;
  title: string;
  created_by_user_id: string;
  created_at: string;
  versions: MemoVersion[];
}

export interface Change {
  field: string;
  kind: "added" | "removed" | "changed";
  before: string | null;
  after: string | null;
  delta: string | null;
}

export interface AssumptionOverrideResult {
  version: MemoVersion;
  change_note: string;
  changes: Change[];
}
