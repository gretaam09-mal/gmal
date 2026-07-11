import { apiFetch } from "@/lib/api";

import type { EntityProfile, FieldCatalogEntry, FieldSource } from "./types";

type GetToken = () => Promise<string | null>;

export const getFieldCatalog = (getToken: GetToken) =>
  apiFetch<FieldCatalogEntry[]>("/profile-field-catalog", { getToken });

export const getProfile = (getToken: GetToken, workspaceId: string) =>
  apiFetch<EntityProfile | null>(`/workspaces/${workspaceId}/profile`, { getToken });

export const listProfileVersions = (getToken: GetToken, workspaceId: string) =>
  apiFetch<EntityProfile[]>(`/workspaces/${workspaceId}/profile/versions`, { getToken });

export const autofillProfile = (
  getToken: GetToken,
  workspaceId: string,
  companiesHouseNumber: string,
) =>
  apiFetch<EntityProfile>(`/workspaces/${workspaceId}/profile/autofill`, {
    method: "POST",
    body: { companies_house_number: companiesHouseNumber },
    getToken,
  });

export interface FieldUpdateInput {
  key: string;
  value: unknown;
  source: FieldSource;
  confirmed_at?: string;
}

export const updateProfile = (getToken: GetToken, workspaceId: string, fields: FieldUpdateInput[]) =>
  apiFetch<EntityProfile>(`/workspaces/${workspaceId}/profile`, {
    method: "PUT",
    body: { fields },
    getToken,
  });
