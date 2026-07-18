import { NextRequest, NextResponse } from "next/server";
import { fetchFromApi } from "@/lib/server-api";

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const upstream = await fetchFromApi(`/api/v1/orchestration/conversations/${id}/turns${request.nextUrl.search}`);
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
