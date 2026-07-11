const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Thin fetch wrapper for the Provision API. `getToken` is Clerk's
 * useAuth().getToken — passed in explicitly so this file has no
 * dependency on being called from a component with Clerk context.
 */
export async function apiFetch<T>(
  path: string,
  options: { method?: string; body?: unknown; getToken: () => Promise<string | null> },
): Promise<T> {
  const token = await options.getToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    const detail = await response
      .json()
      .then((data) => data.detail)
      .catch(() => response.statusText);
    throw new ApiError(response.status, typeof detail === "string" ? detail : response.statusText);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}
