"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";

import { Button } from "@/design-system/components/button";

import { attachCostTemplate, getObligationCostTemplate } from "../api";
import type { CostTemplate } from "../types";

export function CostTemplateForm({ obligationId }: { obligationId: string }) {
  const { getToken } = useAuth();
  const [current, setCurrent] = useState<CostTemplate | null>(null);
  const [name, setName] = useState("");
  const [base, setBase] = useState("0");
  const [driverKey, setDriverKey] = useState("");
  const [rate, setRate] = useState("0");
  const [sourceBasis, setSourceBasis] = useState("expert estimate");
  const [maturityTier, setMaturityTier] = useState("rough");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getObligationCostTemplate(getToken, obligationId).then(setCurrent);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [obligationId]);

  async function handleAttach(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const drivers = driverKey ? [{ key: driverKey, label: driverKey }] : [];
      const formula = driverKey
        ? { base: Number(base), terms: [{ driver: driverKey, rate: Number(rate) }] }
        : { base: Number(base) };
      const created = await attachCostTemplate(getToken, obligationId, {
        name,
        drivers,
        formula,
        currency: "GBP",
        source_basis: sourceBasis,
        maturity_tier: maturityTier,
      });
      setCurrent(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to attach cost template");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <h4 className="font-ui text-sm font-semibold text-ink">Cost template</h4>
      {current ? (
        <div className="rounded-md border border-ink/10 p-3 font-ui text-xs text-ink/70">
          <p className="font-medium text-ink">{current.name}</p>
          <p>
            Base £{String(current.formula.base ?? 0)} · {current.source_basis} · {current.maturity_tier}
          </p>
        </div>
      ) : (
        <p className="font-ui text-xs text-ink/50">No cost template attached yet.</p>
      )}

      <form onSubmit={handleAttach} className="flex flex-col gap-2 rounded-md border border-ink/10 p-3">
        <input
          required
          placeholder="Name (e.g. DPO appointment cost — rough)"
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
        />
        <div className="flex gap-2">
          <input
            placeholder="Base cost (GBP)"
            type="number"
            value={base}
            onChange={(event) => setBase(event.target.value)}
            className="w-32 rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
          />
          <input
            placeholder="Driver field key (optional)"
            value={driverKey}
            onChange={(event) => setDriverKey(event.target.value)}
            className="flex-1 rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
          />
          <input
            placeholder="Rate per unit"
            type="number"
            value={rate}
            onChange={(event) => setRate(event.target.value)}
            className="w-28 rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
          />
        </div>
        <div className="flex gap-2">
          <select
            value={sourceBasis}
            onChange={(event) => setSourceBasis(event.target.value)}
            className="rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
          >
            <option value="expert estimate">expert estimate</option>
            <option value="vendor quote">vendor quote</option>
            <option value="regulatory fee schedule">regulatory fee schedule</option>
          </select>
          <select
            value={maturityTier}
            onChange={(event) => setMaturityTier(event.target.value)}
            className="rounded border border-ink/20 bg-paper px-2 py-1 font-ui text-sm"
          >
            <option value="rough">rough</option>
            <option value="benchmarked">benchmarked</option>
            <option value="quoted">quoted</option>
          </select>
          <Button type="submit" size="dense" disabled={busy}>
            {current ? "Attach new version" : "Attach"}
          </Button>
        </div>
        {error ? <p className="font-ui text-xs text-red-600">{error}</p> : null}
      </form>
    </div>
  );
}
