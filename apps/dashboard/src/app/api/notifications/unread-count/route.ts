import { NextResponse } from "next/server";
import { fetchFromApi } from "@/lib/server-api";

export async function GET() {
  const upstream = await fetchFromApi("/api/v1/notifications/unread-count");
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
