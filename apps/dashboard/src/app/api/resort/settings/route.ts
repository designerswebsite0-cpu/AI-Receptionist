import { NextRequest, NextResponse } from "next/server";
import { fetchFromApi } from "@/lib/server-api";

export async function POST(request: NextRequest) {
  const body = await request.text();
  const upstream = await fetchFromApi("/api/v1/resort/settings", { method: "POST", body });
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}

export async function PATCH(request: NextRequest) {
  const body = await request.text();
  const upstream = await fetchFromApi("/api/v1/resort/settings", { method: "PATCH", body });
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
