import { NextRequest, NextResponse } from "next/server";
import { ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE } from "@/lib/server-api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const PUBLIC_PATHS = ["/login"];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`));
}

/** Centralized route protection (Phase X): every dashboard page used to
 * duplicate its own `getServerAccessToken()` + redirect check — this
 * replaces that with one check at the edge. The access-token cookie's own
 * `maxAge` (set to the token's real `expires_in` at login/refresh) means
 * the browser itself removes it once expired — so "cookie present" here
 * is already a meaningful signal, not just existence-checking. When it's
 * gone but a refresh-token cookie is still valid, this silently exchanges
 * it via the backend's existing `/auth/refresh` (app/auth/router.py) so a
 * guest-facing staff member is never bounced to login just because an
 * hour passed mid-shift. */
export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (isPublicPath(pathname)) {
    // An already-authenticated user hitting /login should land back on
    // the dashboard, not see the login form again.
    if (request.cookies.get(ACCESS_TOKEN_COOKIE)?.value) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    return NextResponse.next();
  }
  if (pathname.startsWith("/api/") || pathname.startsWith("/_next/")) {
    return NextResponse.next();
  }

  const accessToken = request.cookies.get(ACCESS_TOKEN_COOKIE)?.value;
  if (accessToken) {
    return NextResponse.next();
  }

  const refreshToken = request.cookies.get(REFRESH_TOKEN_COOKIE)?.value;
  if (refreshToken) {
    try {
      const upstream = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      const payload = await upstream.json();
      if (upstream.ok && payload.success) {
        const response = NextResponse.next();
        const isProd = process.env.NODE_ENV === "production";
        response.cookies.set(ACCESS_TOKEN_COOKIE, payload.data.access_token, {
          httpOnly: true,
          secure: isProd,
          sameSite: "lax",
          path: "/",
          maxAge: payload.data.expires_in ?? 3600,
        });
        response.cookies.set(REFRESH_TOKEN_COOKIE, payload.data.refresh_token, {
          httpOnly: true,
          secure: isProd,
          sameSite: "lax",
          path: "/",
          maxAge: 60 * 60 * 24 * 30,
        });
        return response;
      }
    } catch {
      // Backend unreachable — fall through to the login redirect below
      // rather than surfacing a raw network error on every route.
    }
  }

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("reason", "expired");
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
