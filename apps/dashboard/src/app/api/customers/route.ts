import { NextRequest, NextResponse } from "next/server";
import { fetchFromApi } from "@/lib/server-api";

export async function GET(request: NextRequest) {
  const upstream = await fetchFromApi(`/api/v1/customers${request.nextUrl.search}`);
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}

export async function POST(request: NextRequest) {
  const body = await request.text();
  const upstream = await fetchFromApi("/api/v1/customers", { method: "POST", body });
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
