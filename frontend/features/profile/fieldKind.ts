export type FieldKind = "boolean" | "number" | "text" | "readonly-list";

const NUMBER_KEYS = new Set([
  "scale.employee_count",
  "scale.annual_revenue_gbp",
  "cost_sketch.compliance_headcount",
  "cost_sketch.annual_compliance_spend_gbp",
  "materiality.threshold_gbp",
]);

const READONLY_LIST_KEYS = new Set(["identity.officers", "activity.sic_codes"]);

export function inferFieldKind(key: string): FieldKind {
  if (key.startsWith("footprint.")) return "boolean";
  if (NUMBER_KEYS.has(key)) return "number";
  if (READONLY_LIST_KEYS.has(key)) return "readonly-list";
  return "text";
}
