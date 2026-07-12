"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/design-system/components/button";

import { createInstrument, listInstruments, listOnboardingMetrics } from "../api";
import type { Instrument, OnboardingMetric } from "../types";

export function InstrumentList() {
  const { getToken } = useAuth();
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [metrics, setMetrics] = useState<OnboardingMetric[]>([]);
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState("Act");
  const [citation, setCitation] = useState("");
  const [rawText, setRawText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setInstruments(await listInstruments(getToken));
    setMetrics(await listOnboardingMetrics(getToken));
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await createInstrument(getToken, {
        title,
        jurisdiction: "UK",
        kind,
        citation: citation || undefined,
        version_label: "v1",
        raw_text: rawText,
      });
      setTitle("");
      setCitation("");
      setRawText("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to ingest instrument");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-8 p-8">
      <header className="flex items-start justify-between">
        <div>
          <h1 className="font-ui text-2xl font-semibold text-ink">Instrument onboarding</h1>
          <p className="font-ui text-sm text-ink/60">
            Internal workbench — never linked from the client app.
          </p>
        </div>
        <Link href="/admin/metrics" className="font-ui text-sm text-primary-navy hover:underline">
          Monthly metrics report →
        </Link>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="font-ui text-lg font-semibold text-ink">Instruments</h2>
        <ul className="flex flex-col gap-2">
          {instruments.map((instrument) => (
            <li key={instrument.id}>
              <Link
                href={`/admin/instruments/${instrument.id}`}
                className="flex items-center justify-between rounded-md border border-ink/10 px-3 py-2 hover:bg-ink/5"
              >
                <div className="flex flex-col">
                  <span className="font-ui text-sm text-ink">{instrument.title}</span>
                  <span className="font-ui text-xs text-ink/50">
                    {instrument.kind} · {instrument.jurisdiction}
                    {instrument.citation ? ` · ${instrument.citation}` : ""}
                  </span>
                </div>
              </Link>
            </li>
          ))}
          {instruments.length === 0 ? (
            <p className="font-ui text-sm text-ink/50">No instruments ingested yet.</p>
          ) : null}
        </ul>
      </section>

      <section className="flex flex-col gap-3 rounded-md border border-ink/10 p-4">
        <h2 className="font-ui text-lg font-semibold text-ink">Ingest a new instrument</h2>
        <form onSubmit={handleCreate} className="flex flex-col gap-2">
          <div className="flex gap-2">
            <input
              required
              placeholder="Title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="flex-1 rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
            />
            <input
              placeholder="Kind (e.g. Act, Regulation)"
              value={kind}
              onChange={(event) => setKind(event.target.value)}
              className="w-48 rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
            />
            <input
              placeholder="Citation (optional)"
              value={citation}
              onChange={(event) => setCitation(event.target.value)}
              className="w-56 rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
            />
          </div>
          <textarea
            required
            rows={8}
            placeholder={"Paste the instrument's text — numbered clauses (\"1. ...\") are segmented automatically."}
            value={rawText}
            onChange={(event) => setRawText(event.target.value)}
            className="rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
          />
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={busy}>
              Ingest &amp; segment
            </Button>
            {error ? <p className="font-ui text-xs text-red-600">{error}</p> : null}
          </div>
        </form>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="font-ui text-lg font-semibold text-ink">Onboarding hours (board metric)</h2>
        <table className="font-ui text-sm">
          <thead>
            <tr className="text-left text-ink/50">
              <th className="pr-4 font-normal">Instrument</th>
              <th className="pr-4 font-normal">Hours</th>
              <th className="font-normal">Completed</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((metric) => (
              <tr key={metric.instrument_id} className="border-t border-ink/5">
                <td className="py-1 pr-4 text-ink">{metric.instrument_title}</td>
                <td className="py-1 pr-4 tabular-nums text-ink">{metric.onboarding_hours.toFixed(2)}</td>
                <td className="py-1 text-ink/60">{new Date(metric.completed_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {metrics.length === 0 ? (
          <p className="font-ui text-sm text-ink/50">No instrument has completed onboarding yet.</p>
        ) : null}
      </section>
    </div>
  );
}
