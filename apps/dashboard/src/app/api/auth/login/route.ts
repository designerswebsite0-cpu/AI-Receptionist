import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE } from "@/lib/server-api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const LoginBody = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

export async function POST(request: NextRequest) {
  const parsed = LoginBody.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json(
      { success: false, error: { code: "VALIDATION_ERROR", message: "Invalid email or password" } },
      { status: 422 }
    );
  }

  const upstream = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(parsed.data),
  });
  const payload = await upstream.json();
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
    maxAge: 60 * 60 * 24 * 30,
  });

  return NextResponse.json({ success: true, data: { logged_in: true } });
}
