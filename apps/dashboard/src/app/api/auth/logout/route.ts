import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, fetchFromApi } from "@/lib/server-api";

export async function POST() {
  await fetchFromApi("/api/v1/auth/logout", { method: "POST" }).catch(() => undefined);

  const store = await cookies();
  store.delete(ACCESS_TOKEN_COOKIE);
  store.delete(REFRESH_TOKEN_COOKIE);

  return NextResponse.json({ success: true, data: { logged_out: true } });
}
