import { NextRequest, NextResponse } from "next/server";
import { fetchFromApi } from "@/lib/server-api";

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const upstream = await fetchFromApi(`/api/v1/knowledge/sources/${id}`);
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await request.text();
  const upstream = await fetchFromApi(`/api/v1/knowledge/sources/${id}`, { method: "PATCH", body });
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
