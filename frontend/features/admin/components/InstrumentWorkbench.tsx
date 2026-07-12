"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";

import { Button } from "@/design-system/components/button";

import { extractObligation, getInstrument, listInstrumentObligations } from "../api";
import type { Clause, InstrumentDetail, Obligation } from "../types";
import { ObligationPanel } from "./ObligationPanel";

export function InstrumentWorkbench({ instrumentId }: { instrumentId: string }) {
  const { getToken } = useAuth();
  const [instrument, setInstrument] = useState<InstrumentDetail | null>(null);
  const [obligationByClauseId, setObligationByClauseId] = useState<Record<string, Obligation>>({});
  const [busyClauseId, setBusyClauseId] = useState<string | null>(null);
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

  return (
    <div className="flex flex-col gap-6 p-8">
      <header>
        <h1 className="font-ui text-2xl font-semibold text-ink">{instrument.title}</h1>
        <p className="font-ui text-sm text-ink/60">
          {instrument.kind} · {instrument.jurisdiction}
          {instrument.citation ? ` · ${instrument.citation}` : ""}
        </p>
      </header>

      {error ? <p className="font-ui text-xs text-red-600">{error}</p> : null}

      <div className="flex flex-col gap-4">
        {clauses.map((clause) => {
          const obligation = obligationByClauseId[clause.id];
          if (!obligation) {
            return (
              <div key={clause.id} className="flex flex-col gap-2 rounded-md border border-ink/10 p-4">
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
            <ObligationPanel
              key={clause.id}
              clause={clause}
              obligation={obligation}
              onObligationChange={(updated) =>
                setObligationByClauseId((prev) => ({ ...prev, [clause.id]: updated }))
              }
            />
          );
        })}
      </div>
    </div>
  );
}
