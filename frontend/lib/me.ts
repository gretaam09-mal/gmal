import { apiFetch } from "@/lib/api";

export interface Me {
  id: string;
  email: string;
  is_staff: boolean;
}

export const getMe = (getToken: () => Promise<string | null>) => apiFetch<Me>("/me", { getToken });
