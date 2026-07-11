export type FieldSource = "registry" | "filing" | "user" | "default" | "estimate" | "unknown";
export type Section = "identity_scale" | "activity" | "footprint" | "cost_sketch" | "materiality";

export interface FieldCatalogEntry {
  key: string;
  section: Section;
  label: string;
  weight: number;
  used_for: string | null;
}

export interface ProfileField {
  key: string;
  value: unknown;
  source: FieldSource;
  confirmed_at: string | null;
}

export interface SectionCompleteness {
  section: Section;
  score: number;
  unknown_field_labels: string[];
}

export interface Completeness {
  overall_score: number;
  sections: SectionCompleteness[];
  unknown_field_labels: string[];
}

export interface EntityProfile {
  id: string;
  workspace_id: string;
  version: number;
  is_current: boolean;
  companies_house_number: string | null;
  created_at: string;
  fields: ProfileField[];
  completeness: Completeness;
}

export const SECTION_LABELS: Record<Section, string> = {
  identity_scale: "Identity & Scale",
  activity: "Activity",
  footprint: "Footprint",
  cost_sketch: "Cost sketch",
  materiality: "Materiality",
};

export const SECTION_ORDER: Section[] = [
  "identity_scale",
  "activity",
  "footprint",
  "cost_sketch",
  "materiality",
];
