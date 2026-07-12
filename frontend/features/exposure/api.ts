import { apiFetch } from "@/lib/api";

import type { Analysis } from "./types";

type GetToken = () => Promise<string | null>;

export const listAnalyses = (getToken: GetToken, workspaceId: string) =>
  apiFetch<Analysis[]>(`/workspaces/${workspaceId}/analyses`, { getToken });

export const runAnalysis = (getToken: GetToken, workspaceId: string) =>
  apiFetch<Analysis>(`/workspaces/${workspaceId}/analyses`, { method: "POST", body: {}, getToken });
