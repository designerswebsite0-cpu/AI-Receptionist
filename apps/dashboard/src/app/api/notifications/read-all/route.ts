import { NextResponse } from "next/server";
import { fetchFromApi } from "@/lib/server-api";

export async function POST() {
  const upstream = await fetchFromApi("/api/v1/notifications/read-all", { method: "POST" });
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
