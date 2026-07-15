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
 * route handlers, which are the only place they're set. */
export async function fetchFromApi(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await getServerAccessToken();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  return fetch(`${API_BASE_URL}${path}`, { ...init, headers, cache: "no-store" });
}
