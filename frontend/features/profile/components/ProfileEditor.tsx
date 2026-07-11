"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/design-system/components/button";

import { autofillProfile, getFieldCatalog, getProfile, updateProfile } from "../api";
import type { FieldUpdateInput } from "../api";
import { SECTION_LABELS, SECTION_ORDER } from "../types";
import type { EntityProfile, FieldCatalogEntry, FieldSource } from "../types";
import { CompletenessMeter } from "./CompletenessMeter";
import { FieldRow } from "./FieldRow";

type PendingEdit = { value: unknown; source: FieldSource };

export function ProfileEditor({ workspaceId }: { workspaceId: string }) {
  const { getToken } = useAuth();
  const [catalog, setCatalog] = useState<FieldCatalogEntry[]>([]);
  const [profile, setProfile] = useState<EntityProfile | null>(null);
  const [pending, setPending] = useState<Record<string, PendingEdit>>({});
  const [companyNumber, setCompanyNumber] = useState("");
  const [activeSection, setActiveSection] = useState(SECTION_ORDER[0]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getFieldCatalog(getToken).then(setCatalog);
    getProfile(getToken, workspaceId).then(setProfile);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  const fieldByKey = useMemo(() => {
    const map = new Map(profile?.fields.map((f) => [f.key, f]));
    return map;
  }, [profile]);

  async function handleAutofill(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const updated = await autofillProfile(getToken, workspaceId, companyNumber);
      setProfile(updated);
      setPending({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Autofill failed");
    } finally {
      setBusy(false);
    }
  }

  function handleFieldChange(key: string, value: unknown, source: FieldSource) {
    setPending((prev) => ({ ...prev, [key]: { value, source } }));
  }

  async function handleSave() {
    setBusy(true);
    setError(null);
    const fields: FieldUpdateInput[] = Object.entries(pending).map(([key, edit]) => ({
      key,
      value: edit.value,
      source: edit.source,
      confirmed_at: edit.source === "user" ? new Date().toISOString() : undefined,
    }));
    try {
      const updated = await updateProfile(getToken, workspaceId, fields);
      setProfile(updated);
      setPending({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  if (!profile) {
    return (
      <form onSubmit={handleAutofill} className="flex max-w-md flex-col gap-2">
        <h2 className="font-ui text-lg font-semibold text-ink">Start with Companies House</h2>
        <p className="font-ui text-sm text-ink/60">
          Enter a company number to auto-fill identity, officers, SIC codes, and scale — or skip
          this and build the profile manually below.
        </p>
        <div className="flex gap-2">
          <input
            required
            placeholder="e.g. 12345678"
            value={companyNumber}
            onChange={(event) => setCompanyNumber(event.target.value)}
            className="flex-1 rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
          />
          <Button type="submit" disabled={busy}>
            Auto-fill
          </Button>
        </div>
        {error ? <p className="font-ui text-xs text-red-600">{error}</p> : null}
      </form>
    );
  }

  const fieldsInSection = catalog.filter((f) => f.section === activeSection);

  return (
    <div className="grid grid-cols-[200px_1fr_240px] gap-6">
      <nav className="flex flex-col gap-1">
        {SECTION_ORDER.map((section) => (
          <button
            key={section}
            onClick={() => setActiveSection(section)}
            className={`rounded-md px-3 py-2 text-left font-ui text-sm ${
              section === activeSection ? "bg-ink/10 text-ink" : "text-ink/60 hover:bg-ink/5"
            }`}
          >
            {SECTION_LABELS[section]}
          </button>
        ))}
      </nav>

      <div className="flex flex-col gap-2 font-document">
        {fieldsInSection.map((spec) => {
          const saved = fieldByKey.get(spec.key);
          const edit = pending[spec.key];
          const displayField = edit
            ? { key: spec.key, value: edit.value, source: edit.source, confirmed_at: null }
            : saved;
          return <FieldRow key={spec.key} spec={spec} field={displayField} onChange={handleFieldChange} />;
        })}

        <div className="flex items-center gap-3 pt-4">
          <Button onClick={handleSave} disabled={busy || Object.keys(pending).length === 0}>
            Save (creates version {profile.version + 1})
          </Button>
          {error ? <p className="font-ui text-xs text-red-600">{error}</p> : null}
        </div>
      </div>

      <CompletenessMeter completeness={profile.completeness} />
    </div>
  );
}
