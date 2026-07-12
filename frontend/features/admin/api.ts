import { apiFetch } from "@/lib/api";

import type {
  CostTemplate,
  Instrument,
  InstrumentDetail,
  MonthlyMetricsReport,
  Obligation,
  ObligationFields,
  OnboardingMetric,
  Predicate,
  PredicateTestResult,
} from "./types";

type GetToken = () => Promise<string | null>;

export const listInstruments = (getToken: GetToken) =>
  apiFetch<Instrument[]>("/admin/instruments", { getToken });

export const getInstrument = (getToken: GetToken, instrumentId: string) =>
  apiFetch<InstrumentDetail>(`/admin/instruments/${instrumentId}`, { getToken });

export const createInstrument = (
  getToken: GetToken,
  body: {
    title: string;
    jurisdiction: string;
    kind: string;
    citation?: string;
    version_label: string;
    source_url?: string;
    raw_text: string;
  },
) => apiFetch<InstrumentDetail>("/admin/instruments", { method: "POST", body, getToken });

export const listInstrumentObligations = (getToken: GetToken, instrumentId: string) =>
  apiFetch<Obligation[]>(`/admin/instruments/${instrumentId}/obligations`, { getToken });

export const extractObligation = (getToken: GetToken, clauseId: string, instrumentTitle: string) =>
  apiFetch<Obligation>(`/admin/clauses/${clauseId}/obligations/extract`, {
    method: "POST",
    body: { instrument_title: instrumentTitle },
    getToken,
  });

export const updateObligation = (
  getToken: GetToken,
  obligationId: string,
  body: Partial<{
    summary: string;
    obligation_type: string;
    fields: ObligationFields;
    confidence: number;
  }>,
) => apiFetch<Obligation>(`/admin/obligations/${obligationId}`, { method: "PATCH", body, getToken });

export const approveObligation = (getToken: GetToken, obligationId: string) =>
  apiFetch<Obligation>(`/admin/obligations/${obligationId}/approve`, { method: "POST", getToken });

export const correctObligation = (
  getToken: GetToken,
  obligationId: string,
  body: { summary: string; obligation_type: string; fields: ObligationFields; confidence: number },
) => apiFetch<Obligation>(`/admin/obligations/${obligationId}/correct`, {
  method: "POST",
  body,
  getToken,
});

export const listObligationPredicates = (getToken: GetToken, obligationId: string) =>
  apiFetch<Predicate[]>(`/admin/obligations/${obligationId}/predicates`, { getToken });

export const draftPredicate = (getToken: GetToken, obligationId: string) =>
  apiFetch<Predicate>(`/admin/obligations/${obligationId}/predicates/draft`, {
    method: "POST",
    getToken,
  });

export const createPredicate = (
  getToken: GetToken,
  obligationId: string,
  body: { predicate_key: string; expression: Record<string, unknown> },
) => apiFetch<Predicate>(`/admin/obligations/${obligationId}/predicates`, {
  method: "POST",
  body,
  getToken,
});

export const updatePredicate = (
  getToken: GetToken,
  predicateId: string,
  expression: Record<string, unknown>,
) =>
  apiFetch<Predicate>(`/admin/predicates/${predicateId}`, {
    method: "PATCH",
    body: { expression },
    getToken,
  });

export const testPredicate = (getToken: GetToken, predicateId: string) =>
  apiFetch<PredicateTestResult[]>(`/admin/predicates/${predicateId}/test`, {
    method: "POST",
    getToken,
  });

export const approvePredicate = (getToken: GetToken, predicateId: string) =>
  apiFetch<Predicate>(`/admin/predicates/${predicateId}/approve`, { method: "POST", getToken });

export const getObligationCostTemplate = (getToken: GetToken, obligationId: string) =>
  apiFetch<CostTemplate | null>(`/admin/obligations/${obligationId}/cost-template`, { getToken });

export const attachCostTemplate = (
  getToken: GetToken,
  obligationId: string,
  body: {
    name: string;
    drivers: { key: string; label: string }[];
    formula: Record<string, unknown>;
    currency: string;
    source_basis: string;
    maturity_tier: string;
  },
) =>
  apiFetch<CostTemplate>(`/admin/obligations/${obligationId}/cost-template`, {
    method: "POST",
    body,
    getToken,
  });

export const listOnboardingMetrics = (getToken: GetToken) =>
  apiFetch<OnboardingMetric[]>("/admin/metrics/onboarding", { getToken });

export const getMonthlyMetricsReport = (getToken: GetToken, year?: number, month?: number) => {
  const params = new URLSearchParams();
  if (year) params.set("year", String(year));
  if (month) params.set("month", String(month));
  const query = params.toString();
  return apiFetch<MonthlyMetricsReport>(
    `/admin/metrics/monthly-report${query ? `?${query}` : ""}`,
    { getToken },
  );
};
