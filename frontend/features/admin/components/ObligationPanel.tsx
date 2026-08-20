"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";

import { Button } from "@/design-system/components/button";

import { approveObligation, listObligationPredicates, updateObligation } from "../api";
import type { Clause, ExtractedField, Obligation, ObligationFields, Predicate } from "../types";
import { CostTemplateForm } from "./CostTemplateForm";
import { PredicateEditor } from "./PredicateEditor";

const FIELD_LABEL: Record<keyof ObligationFields, string> = {
  who: "Who",
  what: "What",
  when: "When",
  threshold: "Threshold",
  enforcer: "Enforcer",
};

// Below this, P-EXTRACT itself is telling you it isn't sure — FR-7 requires
// these are what a reviewer sees and checks first, not buried among fields
// the model was confident about.
export const LOW_CONFIDENCE_THRESHOLD = 70;

// Lowest-confidence field first (FR-7: what needs checking should be first,
// not in a fixed who/what/when order that hides a shaky field at the
// bottom). Approved obligations are read-only history, not a review task,
// so they keep the canonical reading order instead.
function fieldOrderByConfidence(fields: ObligationFields): (keyof ObligationFields)[] {
  return (Object.keys(FIELD_LABEL) as (keyof ObligationFields)[]).sort(
    (a, b) => fields[a].confidence - fields[b].confidence
  );
}

function ExtractedFieldRow({
  label,
  field,
  editable,
  onChange,
}: {
  label: string;
  field: ExtractedField;
  editable: boolean;
  onChange: (field: ExtractedField) => void;
}) {
  const lowConfidence = field.confidence < LOW_CONFIDENCE_THRESHOLD;
  return (
    <div
      className={`grid grid-cols-[80px_1fr_100px_110px] items-start gap-2 py-1 ${
        lowConfidence ? "rounded bg-amber-50" : ""
      }`}
    >
      <span className="font-ui text-xs font-medium text-ink/60">{label}</span>
      {editable ? (
        <textarea
          rows={2}
          value={field.value}
          onChange={(event) => onChange({ ...field, value: event.target.value })}
          className="rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-xs"
        />
      ) : (
        <p className="font-document text-sm text-ink">{field.value}</p>
      )}
      <span className="font-ui text-xs text-ink/40">cl. {field.clause_ref}</span>
      <span
        className={`font-ui text-xs tabular-nums ${
          lowConfidence ? "font-semibold text-amber-700" : "text-ink/40"
        }`}
      >
        {field.confidence}% {lowConfidence ? "— check this" : ""}
      </span>
    </div>
  );
}

export function ObligationPanel({
  clause,
  obligation,
  onObligationChange,
}: {
  clause: Clause;
  obligation: Obligation;
  onObligationChange: (obligation: Obligation) => void;
}) {
  const { getToken } = useAuth();
  const [fields, setFields] = useState<ObligationFields>(obligation.fields);
  const [summary, setSummary] = useState(obligation.summary);
  const [predicates, setPredicates] = useState<Predicate[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setFields(obligation.fields);
    setSummary(obligation.summary);
  }, [obligation]);

  useEffect(() => {
    listObligationPredicates(getToken, obligation.id).then(setPredicates);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [obligation.id]);

  const editable = !obligation.approved;
  const fieldOrder = editable
    ? fieldOrderByConfidence(fields)
    : (Object.keys(FIELD_LABEL) as (keyof ObligationFields)[]);
  const lowConfidenceFields = fieldOrder.filter(
    (key) => fields[key].confidence < LOW_CONFIDENCE_THRESHOLD
  );

  async function handleSave() {
    setBusy(true);
    setError(null);
    try {
      const updated = await updateObligation(getToken, obligation.id, { summary, fields });
      onObligationChange(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove() {
    setBusy(true);
    setError(null);
    try {
      const updated = await approveObligation(getToken, obligation.id);
      onObligationChange(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid grid-cols-2 gap-6 rounded-md border border-ink/10 p-4">
      <div className="flex flex-col gap-2">
        <h3 className="font-ui text-sm font-semibold text-ink">
          Clause {clause.clause_ref}
        </h3>
        <p className="whitespace-pre-wrap font-document text-sm text-ink/80">{clause.text}</p>
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h3 className="font-ui text-sm font-semibold text-ink">Extracted obligation</h3>
          <span
            className={`rounded-full px-2 py-0.5 font-ui text-xs ${
              obligation.approved ? "bg-primary-navy text-paper" : "bg-ink/10 text-ink/70"
            }`}
          >
            {obligation.approved ? "Approved" : "Awaiting review"}
          </span>
        </div>

        {editable ? (
          <textarea
            rows={2}
            value={summary}
            onChange={(event) => setSummary(event.target.value)}
            className="rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
          />
        ) : (
          <p className="font-ui text-sm text-ink">{summary}</p>
        )}

        {editable && lowConfidenceFields.length > 0 ? (
          <p className="rounded bg-amber-50 px-2 py-1 font-ui text-xs text-amber-800">
            {lowConfidenceFields.length === 1 ? "1 field is" : `${lowConfidenceFields.length} fields are`}{" "}
            below {LOW_CONFIDENCE_THRESHOLD}% confidence and shown first below — check{" "}
            {lowConfidenceFields.map((key) => FIELD_LABEL[key]).join(", ")} against the clause text
            before approving.
          </p>
        ) : null}

        <div className="flex flex-col divide-y divide-ink/5">
          {fieldOrder.map((key) => (
            <ExtractedFieldRow
              key={key}
              label={FIELD_LABEL[key]}
              field={fields[key]}
              editable={editable}
              onChange={(field) => setFields((prev) => ({ ...prev, [key]: field }))}
            />
          ))}
        </div>

        {editable ? (
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <Button variant="outline" size="dense" onClick={handleSave} disabled={busy}>
                Save corrections
              </Button>
              <Button size="dense" onClick={handleApprove} disabled={busy}>
                Approve — nothing reaches clients until this is clicked
              </Button>
            </div>
            <p className="font-ui text-xs text-ink/50">
              Before approving: correct any fields flagged above, confirm the summary matches the
              clause, then approve. Predicates and a cost template can be added once approved.
            </p>
          </div>
        ) : null}
        {error ? <p className="font-ui text-xs text-red-600">{error}</p> : null}

        {obligation.approved ? (
          <>
            <hr className="border-ink/10" />
            <PredicateEditor
              obligationId={obligation.id}
              predicates={predicates}
              onPredicatesChange={setPredicates}
            />
            <hr className="border-ink/10" />
            <CostTemplateForm obligationId={obligation.id} />
          </>
        ) : null}
      </div>
    </div>
  );
}
