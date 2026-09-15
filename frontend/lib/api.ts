const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem("somosure_access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...authHeaders(), ...options.headers },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
};

export function storeSession(accessToken: string, refreshToken: string) {
  window.localStorage.setItem("somosure_access_token", accessToken);
  window.localStorage.setItem("somosure_refresh_token", refreshToken);
}

export function clearSession() {
  window.localStorage.removeItem("somosure_access_token");
  window.localStorage.removeItem("somosure_refresh_token");
}

export function isLoggedIn(): boolean {
  if (typeof window === "undefined") return false;
  return !!window.localStorage.getItem("somosure_access_token");
}

// Decodes the JWT payload client-side for UI routing only (e.g. "send staff
// to /admin, customers to /dashboard"). This is NOT a security check - the
// backend re-verifies the signature and role on every request via
// require_roles(); nothing here is trusted for authorization.
export function getTokenRole(): string | null {
  if (typeof window === "undefined") return null;
  const token = window.localStorage.getItem("somosure_access_token");
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.role ?? null;
  } catch {
    return null;
  }
}
