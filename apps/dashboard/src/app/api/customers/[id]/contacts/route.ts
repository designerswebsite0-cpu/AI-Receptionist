import { NextRequest, NextResponse } from "next/server";
import { fetchFromApi } from "@/lib/server-api";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await request.text();
  const upstream = await fetchFromApi(`/api/v1/customers/${id}/contacts`, { method: "POST", body });
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
