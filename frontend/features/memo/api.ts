import { apiFetch, apiFetchBlob } from "@/lib/api";

import type { AssumptionOverrideResult, Memo, MemoVersion, ReviewQueueEntry } from "./types";

type GetToken = () => Promise<string | null>;

export const listMemos = (getToken: GetToken, workspaceId: string) =>
  apiFetch<Memo[]>(`/workspaces/${workspaceId}/memos`, { getToken });

export const createMemo = (
  getToken: GetToken,
  workspaceId: string,
  body: { analysis_id: string; title: string },
) => apiFetch<Memo>(`/workspaces/${workspaceId}/memos`, { method: "POST", body, getToken });

export const getMemo = (getToken: GetToken, workspaceId: string, memoId: string) =>
  apiFetch<Memo>(`/workspaces/${workspaceId}/memos/${memoId}`, { getToken });

export const getReviewQueue = (getToken: GetToken, workspaceId: string) =>
  apiFetch<ReviewQueueEntry[]>(`/workspaces/${workspaceId}/memos/review-queue`, { getToken });

export const setMemoUsedInIc = (
  getToken: GetToken,
  workspaceId: string,
  memoId: string,
  usedInIc: boolean,
) =>
  apiFetch<Memo>(`/workspaces/${workspaceId}/memos/${memoId}/used-in-ic`, {
    method: "PATCH",
    body: { used_in_ic: usedInIc },
    getToken,
  });

export const overrideAssumption = (
  getToken: GetToken,
  workspaceId: string,
  memoId: string,
  versionId: string,
  assumptionId: string,
  body: { value: Record<string, unknown>; note?: string },
) =>
  apiFetch<AssumptionOverrideResult>(
    `/workspaces/${workspaceId}/memos/${memoId}/versions/${versionId}/assumptions/${assumptionId}`,
    { method: "PATCH", body, getToken },
  );

export const submitMemoVersion = (
  getToken: GetToken,
  workspaceId: string,
  memoId: string,
  versionId: string,
) =>
  apiFetch<MemoVersion>(
    `/workspaces/${workspaceId}/memos/${memoId}/versions/${versionId}/submit`,
    { method: "POST", body: {}, getToken },
  );

export const approveMemoVersion = (
  getToken: GetToken,
  workspaceId: string,
  memoId: string,
  versionId: string,
  panelFirm?: string,
) =>
  apiFetch<MemoVersion>(
    `/workspaces/${workspaceId}/memos/${memoId}/versions/${versionId}/approve`,
    { method: "POST", body: { panel_firm: panelFirm || undefined }, getToken },
  );

export const createNewMemoVersion = (
  getToken: GetToken,
  workspaceId: string,
  memoId: string,
  versionId: string,
  changeNote: string,
) =>
  apiFetch<MemoVersion>(
    `/workspaces/${workspaceId}/memos/${memoId}/versions/${versionId}/new-version`,
    { method: "POST", body: { change_note: changeNote }, getToken },
  );

function exportPath(
  workspaceId: string,
  memoId: string,
  versionId: string,
  kind: "pdf" | "docx",
) {
  return `/workspaces/${workspaceId}/memos/${memoId}/versions/${versionId}/export.${kind}`;
}

async function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export async function downloadMemoExport(
  getToken: GetToken,
  workspaceId: string,
  memoId: string,
  versionId: string,
  kind: "pdf" | "docx",
  filename: string,
) {
  const blob = await apiFetchBlob(exportPath(workspaceId, memoId, versionId, kind), { getToken });
  await downloadBlob(blob, filename);
}
