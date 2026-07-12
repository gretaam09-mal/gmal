"use client";

import { useState } from "react";

import { Button } from "@/design-system/components/button";

import type { Assumption } from "../types";

/** Which field of an assumption's value JSON this register edits — a
 * driver/discount-rate/fx-rate assumption has {"value": "..."}, a
 * scenario-probability one has {"probability": "..."}. */
function editableField(assumption: Assumption): string | null {
  if ("value" in assumption.value) return "value";
  if ("probability" in assumption.value) return "probability";
  return null;
}

export function AssumptionRegister({
  assumptions,
  canEdit,
  onOverride,
}: {
  assumptions: Assumption[];
  canEdit: boolean;
  onOverride: (assumption: Assumption, newValue: string, note: string) => Promise<void>;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftValue, setDraftValue] = useState("");
  const [draftNote, setDraftNote] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  function startEdit(assumption: Assumption) {
    const field = editableField(assumption);
    setEditingId(assumption.id);
    setDraftValue(field ? String(assumption.value[field]) : "");
    setDraftNote(assumption.note ?? "");
  }

  async function save(assumption: Assumption) {
    setBusyId(assumption.id);
    try {
      await onOverride(assumption, draftValue, draftNote);
      setEditingId(null);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <table className="w-full border-collapse font-ui text-sm">
      <thead>
        <tr className="border-b border-ink/10 text-left text-xs uppercase tracking-wide text-ink/50">
          <th className="py-2 pr-3">Key</th>
          <th className="py-2 pr-3">Value</th>
          <th className="py-2 pr-3">Source</th>
          <th className="py-2 pr-3">Note</th>
          {canEdit ? <th className="py-2" /> : null}
        </tr>
      </thead>
      <tbody>
        {assumptions.map((assumption) => {
          const field = editableField(assumption);
          const isEditing = editingId === assumption.id;
          return (
            <tr key={assumption.id} className="border-b border-ink/5 align-top">
              <td className="py-2 pr-3 font-mono text-xs text-ink/70">{assumption.key}</td>
              <td className="py-2 pr-3">
                {isEditing ? (
                  <input
                    value={draftValue}
                    onChange={(event) => setDraftValue(event.target.value)}
                    className="w-24 rounded border border-ink/20 bg-paper px-2 py-1 text-xs"
                  />
                ) : field ? (
                  <span className="tabular-nums">{String(assumption.value[field])}</span>
                ) : (
                  <span className="text-ink/50">{JSON.stringify(assumption.value)}</span>
                )}
              </td>
              <td className="py-2 pr-3 text-xs text-ink/60">{assumption.source}</td>
              <td className="py-2 pr-3">
                {isEditing ? (
                  <input
                    value={draftNote}
                    onChange={(event) => setDraftNote(event.target.value)}
                    placeholder="Why this override?"
                    className="w-40 rounded border border-ink/20 bg-paper px-2 py-1 text-xs"
                  />
                ) : (
                  <span className="text-xs text-ink/50">{assumption.note ?? "—"}</span>
                )}
              </td>
              {canEdit ? (
                <td className="py-2">
                  {isEditing ? (
                    <div className="flex gap-1">
                      <Button
                        size="dense"
                        onClick={() => save(assumption)}
                        disabled={busyId === assumption.id}
                      >
                        Save
                      </Button>
                      <Button
                        size="dense"
                        variant="outline"
                        onClick={() => setEditingId(null)}
                        disabled={busyId === assumption.id}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : field ? (
                    <Button size="dense" variant="outline" onClick={() => startEdit(assumption)}>
                      Override
                    </Button>
                  ) : null}
                </td>
              ) : null}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
