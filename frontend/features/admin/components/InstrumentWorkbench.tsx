"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";

import { Button } from "@/design-system/components/button";

import { extractObligation, getInstrument, listInstrumentObligations } from "../api";
import type { Clause, InstrumentDetail, Obligation, ObligationFields } from "../types";
import { LOW_CONFIDENCE_THRESHOLD, ObligationPanel } from "./ObligationPanel";

function lowestFieldConfidence(fields: ObligationFields): number {
  return Math.min(...(Object.values(fields).map((f) => f.confidence) as number[]));
}

export function InstrumentWorkbench({ instrumentId }: { instrumentId: string }) {
  const { getToken } = useAuth();
  const [instrument, setInstrument] = useState<InstrumentDetail | null>(null);
  const [obligationByClauseId, setObligationByClauseId] = useState<Record<string, Obligation>>({});
  const [busyClauseId, setBusyClauseId] = useState<string | null>(null);
  const [helpOpen, setHelpOpen] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const detail = await getInstrument(getToken, instrumentId);
    setInstrument(detail);
    const obligations = await listInstrumentObligations(getToken, instrumentId);
    setObligationByClauseId(Object.fromEntries(obligations.map((o) => [o.clause_id, o])));
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instrumentId]);

  async function handleExtract(clause: Clause) {
    if (!instrument) return;
    setBusyClauseId(clause.id);
    setError(null);
    try {
      const obligation = await extractObligation(getToken, clause.id, instrument.title);
      setObligationByClauseId((prev) => ({ ...prev, [clause.id]: obligation }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Extraction failed");
    } finally {
      setBusyClauseId(null);
    }
  }

  if (!instrument) {
    return <p className="p-8 font-ui text-sm text-ink/60">Loading…</p>;
  }

  const clauses: Clause[] = instrument.versions.flatMap((v) => v.clauses);
  const obligations = Object.values(obligationByClauseId);
  const approvedCount = obligations.filter((o) => o.approved).length;

  const needsAttention = clauses
    .map((clause) => ({ clause, obligation: obligationByClauseId[clause.id] }))
    .filter(({ obligation }) => obligation && !obligation.approved)
    .map(({ clause, obligation }) => ({
      clause,
      obligation: obligation as Obligation,
      lowest: lowestFieldConfidence((obligation as Obligation).fields),
    }))
    .filter(({ lowest }) => lowest < LOW_CONFIDENCE_THRESHOLD)
    .sort((a, b) => a.lowest - b.lowest);

  return (
    <div className="flex flex-col gap-6 p-8">
      <header>
        <h1 className="font-ui text-2xl font-semibold text-ink">{instrument.title}</h1>
        <p className="font-ui text-sm text-ink/60">
          {instrument.kind} · {instrument.jurisdiction}
          {instrument.citation ? ` · ${instrument.citation}` : ""}
        </p>
      </header>

      <details
        className="rounded-md border border-ink/10 bg-ink/[0.02] p-4"
        open={helpOpen}
        onToggle={(event) => setHelpOpen(event.currentTarget.open)}
      >
        <summary className="cursor-pointer font-ui text-sm font-semibold text-ink">
          How to onboard this instrument
        </summary>
        <ol className="mt-2 flex flex-col gap-1 font-ui text-xs text-ink/70">
          <li>1. Paste the instrument&apos;s text (done — {clauses.length} clause(s) segmented).</li>
          <li>2. For each clause below, click &quot;Extract with P-EXTRACT&quot; to draft an obligation.</li>
          <li>
            3. Review the drafted fields — anything below {LOW_CONFIDENCE_THRESHOLD}% confidence is
            highlighted and listed first; correct it against the clause text.
          </li>
          <li>4. Approve the obligation, then author or adjust its applicability predicate(s).</li>
          <li>5. Attach a cost template. Repeat for every clause, then the instrument is ready to use.</li>
        </ol>
      </details>

      <p className="font-ui text-sm text-ink/60">
        {approvedCount} of {clauses.length} clause(s) have an approved obligation.
      </p>

      {needsAttention.length > 0 ? (
        <div className="flex flex-col gap-2 rounded-md border border-amber-200 bg-amber-50 p-4">
          <h2 className="font-ui text-sm font-semibold text-amber-900">
            Needs attention before approval ({needsAttention.length})
          </h2>
          <ul className="flex flex-col gap-1">
            {needsAttention.map(({ clause, lowest }) => (
              <li key={clause.id}>
                <a
                  href={`#clause-${clause.id}`}
                  className="font-ui text-xs text-amber-800 underline underline-offset-2"
                >
                  Clause {clause.clause_ref} — lowest field confidence {lowest}%
                </a>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {error ? <p className="font-ui text-xs text-red-600">{error}</p> : null}

      <div className="flex flex-col gap-4">
        {clauses.map((clause) => {
          const obligation = obligationByClauseId[clause.id];
          if (!obligation) {
            return (
              <div
                key={clause.id}
                id={`clause-${clause.id}`}
                className="flex flex-col gap-2 rounded-md border border-ink/10 p-4"
              >
                <h3 className="font-ui text-sm font-semibold text-ink">Clause {clause.clause_ref}</h3>
                <p className="whitespace-pre-wrap font-document text-sm text-ink/80">{clause.text}</p>
                <div>
                  <Button
                    size="dense"
                    onClick={() => handleExtract(clause)}
                    disabled={busyClauseId === clause.id}
                  >
                    Extract with P-EXTRACT
                  </Button>
                </div>
              </div>
            );
          }
          return (
            <div key={clause.id} id={`clause-${clause.id}`}>
              <ObligationPanel
                clause={clause}
                obligation={obligation}
                onObligationChange={(updated) =>
                  setObligationByClauseId((prev) => ({ ...prev, [clause.id]: updated }))
                }
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
