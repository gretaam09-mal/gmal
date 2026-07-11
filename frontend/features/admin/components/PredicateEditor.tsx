"use client";

import { useAuth } from "@clerk/nextjs";
import { useState } from "react";

import { Button } from "@/design-system/components/button";

import {
  approvePredicate,
  createPredicate,
  draftPredicate,
  testPredicate,
  updatePredicate,
} from "../api";
import type { Predicate, PredicateTestResult } from "../types";

const OUTCOME_LABEL: Record<PredicateTestResult["outcome"], string> = {
  binds: "Binds",
  does_not_bind: "Does not bind",
  ambiguous: "Ambiguous",
};

function PredicateRow({
  predicate,
  onChange,
}: {
  predicate: Predicate;
  onChange: (updated: Predicate) => void;
}) {
  const { getToken } = useAuth();
  const [expressionText, setExpressionText] = useState(JSON.stringify(predicate.expression, null, 2));
  const [results, setResults] = useState<PredicateTestResult[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isDraft = predicate.status === "draft";

  async function handleSaveExpression() {
    setBusy(true);
    setError(null);
    try {
      const parsed = JSON.parse(expressionText);
      const updated = await updatePredicate(getToken, predicate.id, parsed);
      onChange(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid expression");
    } finally {
      setBusy(false);
    }
  }

  async function handleTest() {
    setBusy(true);
    setError(null);
    try {
      setResults(await testPredicate(getToken, predicate.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test run failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove() {
    setBusy(true);
    setError(null);
    try {
      const updated = await approvePredicate(getToken, predicate.id);
      onChange(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border border-ink/10 p-3">
      <div className="flex items-center justify-between">
        <span className="font-ui text-sm font-medium text-ink">{predicate.predicate_key}</span>
        <div className="flex items-center gap-2">
          {predicate.drafted_by_ai ? (
            <span className="rounded-full bg-ink/5 px-2 py-0.5 font-ui text-xs text-ink/60">
              P-PREDICATE-ASSIST draft
            </span>
          ) : null}
          <span
            className={`rounded-full px-2 py-0.5 font-ui text-xs ${
              predicate.status === "approved"
                ? "bg-primary-navy text-paper"
                : "bg-ink/10 text-ink/70"
            }`}
          >
            {predicate.status}
          </span>
        </div>
      </div>

      <textarea
        rows={5}
        value={expressionText}
        disabled={!isDraft}
        onChange={(event) => setExpressionText(event.target.value)}
        className="rounded border border-ink/20 bg-paper px-2 py-1 font-mono text-xs disabled:opacity-60"
      />

      <div className="flex flex-wrap items-center gap-2">
        {isDraft ? (
          <Button variant="outline" size="dense" onClick={handleSaveExpression} disabled={busy}>
            Save edits
          </Button>
        ) : null}
        <Button variant="outline" size="dense" onClick={handleTest} disabled={busy}>
          Run against fixture profiles
        </Button>
        {isDraft ? (
          <Button size="dense" onClick={handleApprove} disabled={busy}>
            Approve
          </Button>
        ) : null}
        {error ? <p className="font-ui text-xs text-red-600">{error}</p> : null}
      </div>

      {results ? (
        <ul className="flex flex-col gap-1">
          {results.map((result) => (
            <li key={result.profile_name} className="flex items-center gap-2 font-ui text-xs">
              <span className="w-48 text-ink/70">{result.profile_name}</span>
              <span
                className={
                  result.outcome === "binds"
                    ? "text-emerald-700"
                    : result.outcome === "does_not_bind"
                      ? "text-ink/50"
                      : "text-amber-700"
                }
              >
                {OUTCOME_LABEL[result.outcome]}
              </span>
              {result.missing_field_keys.length > 0 ? (
                <span className="text-ink/40">({result.missing_field_keys.join(", ")})</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function PredicateEditor({
  obligationId,
  predicates,
  onPredicatesChange,
}: {
  obligationId: string;
  predicates: Predicate[];
  onPredicatesChange: (predicates: Predicate[]) => void;
}) {
  const { getToken } = useAuth();
  const [predicateKey, setPredicateKey] = useState("");
  const [expressionText, setExpressionText] = useState('{"field": "", "equals": true}');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function replaceOrAppend(updated: Predicate) {
    const exists = predicates.some((p) => p.id === updated.id);
    onPredicatesChange(exists ? predicates.map((p) => (p.id === updated.id ? updated : p)) : [...predicates, updated]);
  }

  async function handleDraft() {
    setBusy(true);
    setError(null);
    try {
      const drafted = await draftPredicate(getToken, obligationId);
      replaceOrAppend(drafted);
    } catch (err) {
      setError(err instanceof Error ? err.message : "P-PREDICATE-ASSIST failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateManual(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const parsed = JSON.parse(expressionText);
      const created = await createPredicate(getToken, obligationId, {
        predicate_key: predicateKey,
        expression: parsed,
      });
      replaceOrAppend(created);
      setPredicateKey("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid expression");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <h4 className="font-ui text-sm font-semibold text-ink">Predicates</h4>
      {predicates.map((predicate) => (
        <PredicateRow key={predicate.id} predicate={predicate} onChange={replaceOrAppend} />
      ))}

      <div className="flex items-center gap-2">
        <Button variant="outline" size="dense" onClick={handleDraft} disabled={busy}>
          Draft with P-PREDICATE-ASSIST
        </Button>
      </div>

      <form onSubmit={handleCreateManual} className="flex flex-col gap-2 rounded-md border border-ink/10 p-3">
        <h5 className="font-ui text-xs font-medium text-ink/70">Or write one by hand</h5>
        <input
          required
          placeholder="predicate_key"
          value={predicateKey}
          onChange={(event) => setPredicateKey(event.target.value)}
          className="rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
        />
        <textarea
          rows={3}
          value={expressionText}
          onChange={(event) => setExpressionText(event.target.value)}
          className="rounded border border-ink/20 bg-paper px-2 py-1 font-mono text-xs"
        />
        <div>
          <Button type="submit" size="dense" disabled={busy}>
            Add draft predicate
          </Button>
        </div>
      </form>
      {error ? <p className="font-ui text-xs text-red-600">{error}</p> : null}
    </div>
  );
}
