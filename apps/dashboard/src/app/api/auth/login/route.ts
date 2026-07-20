import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE } from "@/lib/server-api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const LoginBody = z.object({
  email: z.string().email(),
  password: z.string().min(1),
  remember_session: z.boolean().optional().default(true),
});

type LoginUpstreamPayload =
  | { success: true; data: { access_token: string; refresh_token: string; expires_in?: number } }
  | { success: false; error: { code: string; message: string } };

export async function POST(request: NextRequest) {
  const parsed = LoginBody.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json(
      { success: false, error: { code: "VALIDATION_ERROR", message: "Invalid email or password" } },
      { status: 422 }
    );
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: parsed.data.email, password: parsed.data.password }),
    });
  } catch (err) {
    // The backend didn't respond at all (down, unreachable, DNS failure,
    // NEXT_PUBLIC_API_BASE_URL misconfigured) — this previously surfaced
    // as an unhandled exception here, which Next.js turns into a bare 500
    // with no JSON body, so the login page's error message fell through
    // to a generic "something went wrong" with no way to tell this apart
    // from a wrong password. Logged server-side, never shown to the guest.
    console.error("[auth:login] upstream unreachable", { apiBaseUrl: API_BASE_URL, err });
    return NextResponse.json(
      {
        success: false,
        error: { code: "UPSTREAM_UNREACHABLE", message: "Our server is temporarily unavailable. Please try again shortly." },
      },
      { status: 502 },
    );
  }

  let payload: LoginUpstreamPayload;
  try {
    payload = await upstream.json();
  } catch (err) {
    console.error("[auth:login] upstream returned a non-JSON response", { status: upstream.status, err });
    return NextResponse.json(
      {
        success: false,
        error: { code: "UPSTREAM_UNREACHABLE", message: "Our server is temporarily unavailable. Please try again shortly." },
      },
      { status: 502 },
    );
  }

  if (!upstream.ok || !payload.success) {
    return NextResponse.json(payload, { status: upstream.status });
  }

  const store = await cookies();
  const isProd = process.env.NODE_ENV === "production";
  store.set(ACCESS_TOKEN_COOKIE, payload.data.access_token, {
    httpOnly: true,
    secure: isProd,
    sameSite: "lax",
    path: "/",
    maxAge: payload.data.expires_in ?? 3600,
  });
  store.set(REFRESH_TOKEN_COOKIE, payload.data.refresh_token, {
    httpOnly: true,
    secure: isProd,
    sameSite: "lax",
    path: "/",
    // "Remember this session" unchecked -> a browser-session cookie (no
    // maxAge at all) that disappears when the browser closes, instead of
    // persisting for 30 days.
    ...(parsed.data.remember_session ? { maxAge: 60 * 60 * 24 * 30 } : {}),
  });

  return NextResponse.json({ success: true, data: { logged_in: true } });
}
