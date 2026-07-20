import { NextRequest, NextResponse } from "next/server";
import { fetchFromApi } from "@/lib/server-api";

export async function GET(request: NextRequest) {
  const search = request.nextUrl.search;
  const upstream = await fetchFromApi(`/api/v1/audit/logs${search}`);
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
