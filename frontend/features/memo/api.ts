import { apiFetch } from "@/lib/api";

import type { AssumptionOverrideResult, Memo, MemoVersion } from "./types";

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
) =>
  apiFetch<MemoVersion>(
    `/workspaces/${workspaceId}/memos/${memoId}/versions/${versionId}/approve`,
    { method: "POST", body: {}, getToken },
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
