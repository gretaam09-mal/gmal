"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/design-system/components/button";
import { listAnalyses } from "@/features/exposure/api";
import type { Role } from "@/features/workspaces/types";

import {
  approveMemoVersion,
  createMemo,
  createNewMemoVersion,
  listMemos,
  overrideAssumption,
  submitMemoVersion,
} from "../api";
import type { Assumption, Change, Memo, MemoVersion } from "../types";
import { AssumptionRegister } from "./AssumptionRegister";
import { ExcludedSection } from "./ExcludedSection";
import { ObligationCard } from "./ObligationCard";
import { RangeBar } from "./RangeBar";
import { StatusBadge } from "./StatusBadge";
import { Waterfall } from "./Waterfall";

const CAN_DRAFT: Role[] = ["owner", "analyst"];
const CAN_APPROVE: Role[] = ["owner", "approver"];

function latestVersion(memo: Memo): MemoVersion | null {
  return memo.versions[memo.versions.length - 1] ?? null;
}

export function MemoView({ workspaceId, myRole }: { workspaceId: string; myRole: Role | null }) {
  const { getToken } = useAuth();
  const [memo, setMemo] = useState<Memo | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastDiff, setLastDiff] = useState<{ note: string; changes: Change[] } | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [memos, analyses] = await Promise.all([
        listMemos(getToken, workspaceId),
        listAnalyses(getToken, workspaceId),
      ]);
      setMemo(memos[0] ?? null);
      setAnalysisId(analyses[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load memo");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleCreate() {
    if (!analysisId) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createMemo(getToken, workspaceId, {
        analysis_id: analysisId,
        title: "Impact Memo",
      });
      setMemo(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create memo");
    } finally {
      setBusy(false);
    }
  }

  async function handleOverride(assumption: Assumption, newValue: string, note: string) {
    if (!memo) return;
    const version = latestVersion(memo);
    if (!version) return;
    const field = "value" in assumption.value ? "value" : "probability";
    setError(null);
    try {
      const result = await overrideAssumption(
        getToken,
        workspaceId,
        memo.id,
        version.id,
        assumption.id,
        { value: { ...assumption.value, [field]: newValue }, note: note || undefined },
      );
      setMemo({
        ...memo,
        versions: memo.versions.map((v) => (v.id === result.version.id ? result.version : v)),
      });
      setLastDiff({ note: result.change_note, changes: result.changes });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Override failed");
      throw err;
    }
  }

  async function handleSubmit() {
    if (!memo) return;
    const version = latestVersion(memo);
    if (!version) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await submitMemoVersion(getToken, workspaceId, memo.id, version.id);
      setMemo({
        ...memo,
        versions: memo.versions.map((v) => (v.id === updated.id ? updated : v)),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove() {
    if (!memo) return;
    const version = latestVersion(memo);
    if (!version) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await approveMemoVersion(getToken, workspaceId, memo.id, version.id);
      setMemo({
        ...memo,
        versions: memo.versions.map((v) => (v.id === updated.id ? updated : v)),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleNewVersion() {
    if (!memo) return;
    const version = latestVersion(memo);
    if (!version) return;
    const changeNote = window.prompt("Describe why a new version is needed:");
    if (!changeNote) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createNewMemoVersion(
        getToken,
        workspaceId,
        memo.id,
        version.id,
        changeNote,
      );
      setMemo({ ...memo, versions: [...memo.versions, created] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create new version");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <p className="font-ui text-sm text-ink/60">Loading memo…</p>;
  }

  if (!memo) {
    return (
      <div className="flex flex-col gap-3">
        {error ? <p className="font-ui text-xs text-red-600">{error}</p> : null}
        {analysisId ? (
          <>
            <p className="font-ui text-sm text-ink/60">No Impact Memo yet for this analysis.</p>
            <Button size="dense" onClick={handleCreate} disabled={busy}>
              Create Impact Memo
            </Button>
          </>
        ) : (
          <p className="font-ui text-sm text-ink/60">
            Run an analysis first — the memo composes from its results.
          </p>
        )}
      </div>
    );
  }

  const version = latestVersion(memo);
  if (!version) return null;
  const { content } = version;
  const canDraft = myRole ? CAN_DRAFT.includes(myRole) : false;
  const canApprove = myRole ? CAN_APPROVE.includes(myRole) : false;

  return (
    <div className="flex flex-col gap-6 bg-paper font-document">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-ui text-lg font-semibold text-ink">{memo.title}</h2>
          <p className="font-ui text-xs text-ink/50">
            Version {version.version} · Confidence grade {content.confidence_grade}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={version.status} />
          {version.status === "draft" && canDraft ? (
            <Button size="dense" onClick={handleSubmit} disabled={busy}>
              Submit for review
            </Button>
          ) : null}
          {version.status === "in_review" && canApprove ? (
            <Button size="dense" onClick={handleApprove} disabled={busy}>
              Approve
            </Button>
          ) : null}
          {version.status === "approved" && canDraft ? (
            <Button size="dense" variant="outline" onClick={handleNewVersion} disabled={busy}>
              Create new version
            </Button>
          ) : null}
        </div>
      </div>

      {error ? <p className="font-ui text-xs text-red-600">{error}</p> : null}

      {content.change_note ? (
        <p className="rounded-md bg-amber-50 p-3 font-ui text-xs text-amber-800">
          Supersedes version {content.superseded_version}: {content.change_note}
        </p>
      ) : null}

      <section className="flex flex-col gap-3 rounded-md border border-ink/10 p-4">
        <h3 className="font-ui text-sm font-medium text-ink">Headline exposure</h3>
        <RangeBar
          low={content.headline.low}
          likely={content.headline.likely}
          high={content.headline.high}
          currency={content.headline.currency}
        />
        <p className="font-document text-sm text-ink/80">{content.headline_summary}</p>
      </section>

      {content.obligations.length > 0 ? (
        <section className="flex flex-col gap-3 rounded-md border border-ink/10 p-4">
          <h3 className="font-ui text-sm font-medium text-ink">Composition of the range</h3>
          <Waterfall obligations={content.obligations} currency={content.headline.currency} />
        </section>
      ) : null}

      <section className="flex flex-col gap-3">
        <h3 className="font-ui text-sm font-medium text-ink">Obligations</h3>
        {content.obligations.map((obligation) => (
          <ObligationCard key={obligation.predicate_id} obligation={obligation} />
        ))}
      </section>

      <ExcludedSection excluded={content.excluded} summary={content.excluded_summary} />

      <section className="flex flex-col gap-3 rounded-md border border-ink/10 p-4">
        <h3 className="font-ui text-sm font-medium text-ink">Assumption register</h3>
        <AssumptionRegister
          assumptions={version.assumptions}
          canEdit={canDraft && version.status !== "approved"}
          onOverride={handleOverride}
        />
      </section>

      {lastDiff ? (
        <section className="flex flex-col gap-2 rounded-md border border-primary-navy/20 bg-primary-navy/5 p-4">
          <h3 className="font-ui text-sm font-medium text-ink">What changed</h3>
          <p className="font-document text-sm text-ink/80">{lastDiff.note}</p>
          <ul className="flex flex-col gap-1">
            {lastDiff.changes.map((change) => (
              <li key={change.field} className="font-ui text-xs tabular-nums text-ink/60">
                {change.field}: {change.before ?? "—"} → {change.after ?? "—"}
                {change.delta ? ` (Δ ${change.delta})` : ""}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
