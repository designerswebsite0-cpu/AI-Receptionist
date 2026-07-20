import { NextRequest, NextResponse } from "next/server";
import { fetchFromApi } from "@/lib/server-api";

export async function DELETE(_request: NextRequest, { params }: { params: Promise<{ id: string; tag: string }> }) {
  const { id, tag } = await params;
  const upstream = await fetchFromApi(`/api/v1/customers/${id}/tags/${encodeURIComponent(tag)}`, {
    method: "DELETE",
  });
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
