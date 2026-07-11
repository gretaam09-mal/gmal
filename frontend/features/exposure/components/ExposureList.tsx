"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/design-system/components/button";
import { getFieldCatalog } from "@/features/profile/api";
import type { FieldCatalogEntry } from "@/features/profile/types";

import { listAnalyses, runAnalysis } from "../api";
import type { Analysis } from "../types";
import { ExposureRow } from "./ExposureRow";

/**
 * F4's screen: ranked binds/ambiguous rows first (the inclusions and the
 * open questions), does-not-bind folded but one click away (exclusions
 * are half the value — see docs/CONVENTIONS.md and the F4 spec — never
 * hidden deeper than a fold). Light document theme: paper background,
 * serif body copy for the narrative bits, sans for chrome — matching
 * design-system/tokens.ts.
 */
export function ExposureList({
  workspaceId,
  onNavigateToProfileField,
}: {
  workspaceId: string;
  onNavigateToProfileField?: (fieldKey: string) => void;
}) {
  const { getToken } = useAuth();
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [catalog, setCatalog] = useState<FieldCatalogEntry[]>([]);
  const [exclusionsOpen, setExclusionsOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getFieldCatalog(getToken).then(setCatalog);
    listAnalyses(getToken, workspaceId).then((analyses) => setAnalysis(analyses[0] ?? null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  const fieldLabel = useMemo(() => {
    const byKey = new Map(catalog.map((f) => [f.key, f.label]));
    return (key: string) => byKey.get(key) ?? key;
  }, [catalog]);

  async function handleRun() {
    setBusy(true);
    setError(null);
    try {
      setAnalysis(await runAnalysis(getToken, workspaceId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setBusy(false);
    }
  }

  const included = analysis?.items.filter((i) => i.outcome !== "does_not_bind") ?? [];
  const excluded = analysis?.items.filter((i) => i.outcome === "does_not_bind") ?? [];

  return (
    <div className="flex flex-col gap-4 bg-paper font-document">
      <div className="flex items-center justify-between">
        <h2 className="font-ui text-lg font-semibold text-ink">Exposure list</h2>
        <Button size="dense" onClick={handleRun} disabled={busy}>
          {analysis ? "Re-run analysis" : "Run analysis"}
        </Button>
      </div>
      {error ? <p className="font-ui text-xs text-red-600">{error}</p> : null}

      {!analysis ? (
        <p className="font-ui text-sm text-ink/60">
          No analysis yet — run one against the current entity profile.
        </p>
      ) : analysis.items.length === 0 ? (
        <p className="font-ui text-sm text-ink/60">
          No approved predicates exist yet to evaluate — see the instrument-onboarding workbench.
        </p>
      ) : (
        <>
          <div className="flex flex-col">
            {included.length === 0 ? (
              <p className="font-ui text-sm text-ink/50">Nothing binds or is ambiguous.</p>
            ) : (
              included.map((item) => (
                <ExposureRow
                  key={item.id}
                  item={item}
                  fieldLabel={fieldLabel}
                  onNavigateToProfileField={onNavigateToProfileField}
                />
              ))
            )}
          </div>

          <div className="flex flex-col gap-2 rounded-md border border-ink/10">
            <button
              type="button"
              onClick={() => setExclusionsOpen((v) => !v)}
              className="flex items-center justify-between px-4 py-2 font-ui text-sm text-ink/70 hover:bg-ink/5"
            >
              <span>
                Exclusions ({excluded.length}) — instruments assessed and found not to apply
              </span>
              <span>{exclusionsOpen ? "Hide" : "Show"}</span>
            </button>
            {exclusionsOpen ? (
              <div className="flex flex-col px-4 pb-2">
                {excluded.map((item) => (
                  <ExposureRow key={item.id} item={item} fieldLabel={fieldLabel} />
                ))}
              </div>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}
