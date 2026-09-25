const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Login/register define their own pass/fail around credentials, not
// session validity - a wrong password there is a normal 401, not an
// expired session, so those two are excluded from the auto-logout below.
const AUTH_ENDPOINTS = ["/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh"];

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
  if (res.status === 401 && !AUTH_ENDPOINTS.some((p) => path.startsWith(p))) {
    clearSession();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Your session has expired - please log in again.");
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
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
function getTokenPayload(): Record<string, unknown> | null {
  if (typeof window === "undefined") return null;
  const token = window.localStorage.getItem("somosure_access_token");
  if (!token) return null;
  try {
    return JSON.parse(atob(token.split(".")[1]));
  } catch {
    return null;
  }
}

export function getTokenRole(): string | null {
  const payload = getTokenPayload();
  return (payload?.role as string) ?? null;
}

export function getTokenUserId(): string | null {
  const payload = getTokenPayload();
  return (payload?.sub as string) ?? null;
}

// True once the token's own "exp" claim (seconds since epoch) is in the
// past. This is a client-side convenience check only, so pages that make
// no API call on load (e.g. a static admin landing page) can still notice
// an expired token instead of rendering as if the session were live - the
// backend is still the real authority and re-verifies on every request.
export function isTokenExpired(): boolean {
  const payload = getTokenPayload();
  const exp = payload?.exp as number | undefined;
  if (!exp) return false;
  return Date.now() >= exp * 1000;
}

// The single source of truth for "is this a usable session right now" -
// used by AuthGuard to decide whether to render a protected route or bounce
// to /login. Combines presence + expiry so callers don't have to.
export function hasValidSession(): boolean {
  if (typeof window === "undefined") return false;
  if (!window.localStorage.getItem("somosure_access_token")) return false;
  return !isTokenExpired();
}