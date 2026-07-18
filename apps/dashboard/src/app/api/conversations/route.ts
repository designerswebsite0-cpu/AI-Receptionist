import { NextRequest, NextResponse } from "next/server";
import { fetchFromApi } from "@/lib/server-api";

export async function GET(request: NextRequest) {
  const upstream = await fetchFromApi(`/api/v1/conversations${request.nextUrl.search}`);
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
