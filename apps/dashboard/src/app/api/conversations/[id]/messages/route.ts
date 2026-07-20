import { NextRequest, NextResponse } from "next/server";
import { fetchFromApi } from "@/lib/server-api";

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const upstream = await fetchFromApi(`/api/v1/conversations/${id}/messages${request.nextUrl.search}`);
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await request.text();
  const upstream = await fetchFromApi(`/api/v1/conversations/${id}/messages`, { method: "POST", body });
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
