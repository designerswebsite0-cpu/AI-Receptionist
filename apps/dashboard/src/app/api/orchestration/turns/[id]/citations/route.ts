import { NextRequest, NextResponse } from "next/server";
import { fetchFromApi } from "@/lib/server-api";

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const upstream = await fetchFromApi(`/api/v1/orchestration/turns/${id}/citations`);
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
