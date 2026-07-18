import { NextRequest, NextResponse } from "next/server";
import { fetchFromApi } from "@/lib/server-api";

export async function POST(request: NextRequest) {
  const body = await request.text();
  const upstream = await fetchFromApi("/api/v1/knowledge/search", { method: "POST", body });
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
