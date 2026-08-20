import { apiFetch } from "@/lib/api";

export interface Me {
  id: string;
  email: string;
  is_staff: boolean;
  /** Self-diagnostic for PROVISION_ADMIN_EMAILS elevation — see backend/api/routes/me.py. */
  admin_emails_configured: boolean;
  email_matches_admin_list: boolean;
}

export const getMe = (getToken: () => Promise<string | null>) => apiFetch<Me>("/me", { getToken });
