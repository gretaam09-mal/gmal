"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";

import { getMonthlyMetricsReport } from "../api";
import type { MonthlyMetricsReport } from "../types";

function formatMinutes(value: number | null): string {
  return value === null ? "—" : `${value.toFixed(1)} min`;
}

function formatHours(value: number | null): string {
  return value === null ? "—" : `${value.toFixed(1)} hrs`;
}

export function MonthlyMetricsView() {
  const { getToken } = useAuth();
  const [report, setReport] = useState<MonthlyMetricsReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMonthlyMetricsReport(getToken)
      .then(setReport)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load report"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-col gap-8 p-8">
      <header>
        <h1 className="font-ui text-2xl font-semibold text-ink">Monthly metrics report</h1>
        <p className="font-ui text-sm text-ink/60">
          Generated without manual collation — every figure below reads directly off recorded
          board-metric events.
        </p>
      </header>

      {error ? <p className="font-ui text-xs text-red-600">{error}</p> : null}

      {report ? (
        <>
          <p className="font-ui text-sm text-ink/50">
            {new Date(report.period_start).toLocaleDateString()} –{" "}
            {new Date(report.period_end).toLocaleDateString()}
          </p>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <MetricTile label="Time to exposure list" value={formatMinutes(report.time_to_exposure_list_minutes_avg)} />
            <MetricTile label="Time to approved memo" value={formatMinutes(report.time_to_approved_memo_minutes_avg)} />
            <MetricTile label="Review minutes" value={formatMinutes(report.review_minutes_avg)} />
            <MetricTile label="Onboarding hours" value={formatHours(report.onboarding_hours_avg)} />
            <MetricTile label="Assumption overrides" value={String(report.override_count)} />
            <MetricTile label="Memos approved" value={String(report.memos_approved_count)} />
            <MetricTile label="Used in IC" value={String(report.used_in_ic_count)} />
          </dl>
        </>
      ) : error ? null : (
        <p className="font-ui text-sm text-ink/60">Loading…</p>
      )}
    </div>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border border-ink/10 p-4">
      <dt className="font-ui text-xs uppercase tracking-wide text-ink/50">{label}</dt>
      <dd className="font-ui text-xl tabular-nums text-ink">{value}</dd>
    </div>
  );
}
