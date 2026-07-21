import { cookies } from "next/headers";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const ACCESS_TOKEN_COOKIE = "art_access_token";
export const REFRESH_TOKEN_COOKIE = "art_refresh_token";

export async function getServerAccessToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(ACCESS_TOKEN_COOKIE)?.value ?? null;
}

/** Server-side only: attaches the httpOnly access-token cookie as a Bearer
 * header. Tokens never reach client-side JavaScript — see the /api/auth
 * route handlers, which are the only place they're set.
 *
 * `revalidateSeconds` opts a specific call into Next.js's Data Cache
 * instead of the default `no-store` — every other call stays uncached
 * (staff need fresh conversation/booking/customer data on every
 * navigation). Only use this for data that's genuinely fine to be a few
 * seconds stale, e.g. DashboardLayout's own `/auth/me` check, which
 * otherwise re-hits the backend on every single navigation before the
 * page's own data even starts loading. Safe across staff accounts: Next's
 * Data Cache keys on the full request signature including headers, so a
 * different Bearer token (a different logged-in user) is a different
 * cache entry, never a cross-user hit. */
export async function fetchFromApi(
  path: string,
  init: RequestInit = {},
  options?: { revalidateSeconds?: number },
): Promise<Response> {
  const token = await getServerAccessToken();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const cacheInit: Partial<RequestInit> = options?.revalidateSeconds
    ? { next: { revalidate: options.revalidateSeconds } }
    : { cache: "no-store" };

  return fetch(`${API_BASE_URL}${path}`, { ...init, headers, ...cacheInit });
}
