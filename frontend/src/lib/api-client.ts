import { isLoggedIn } from "@/lib/session";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

function doFetch(path: string, init?: RequestInit) {
  return fetch(`${API}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res = await doFetch(path, init);
  // 401 → try a silent token refresh, but only when a session ever existed —
  // guests would just generate a second doomed request.
  if (res.status === 401 && !path.startsWith("/api/v1/auth/") && isLoggedIn() !== false) {
    const refreshed = await doFetch("/api/v1/auth/refresh", { method: "POST" });
    if (refreshed.ok) res = await doFetch(path, init);
  }
  if (!res.ok) {
    let code = "error";
    let message = res.statusText;
    try {
      const body = await res.json();
      code = body.error?.code ?? code;
      message = body.error?.message ?? message;
    } catch {}
    throw new ApiError(res.status, code, message);
  }
  return res.json();
}
