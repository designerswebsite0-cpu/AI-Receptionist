import { NextRequest, NextResponse } from "next/server";
import { getServerAccessToken } from "@/lib/server-api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Multipart bodies can't go through fetchFromApi — it forces
 * Content-Type: application/json, which would strip the multipart
 * boundary. This forwards the browser's FormData as-is, only adding the
 * Authorization header, and lets fetch set its own Content-Type. */
export async function POST(request: NextRequest) {
  const token = await getServerAccessToken();
  const formData = await request.formData();

  const upstream = await fetch(`${API_BASE_URL}/api/v1/knowledge/sources/upload`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: formData,
  });
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
