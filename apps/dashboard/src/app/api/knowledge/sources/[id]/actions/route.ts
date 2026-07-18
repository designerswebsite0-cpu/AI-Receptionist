import { NextRequest, NextResponse } from "next/server";
import { fetchFromApi } from "@/lib/server-api";

const VALID_ACTIONS = new Set(["approve", "reject", "activate", "archive"]);

/** Consolidates the backend's 4 separate action endpoints into one route
 * for the dashboard's action buttons — a dashboard-layer convenience,
 * not a change to the backend API itself (see app/knowledge/router.py,
 * which still exposes each action as its own endpoint). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await request.json();
  const action = body?.action;

  if (typeof action !== "string" || !VALID_ACTIONS.has(action)) {
    return NextResponse.json(
      { success: false, error: { code: "VALIDATION_ERROR", message: "Invalid action" } },
      { status: 422 },
    );
  }

  const upstream = await fetchFromApi(`/api/v1/knowledge/sources/${id}/${action}`, {
    method: "POST",
    body: action === "reject" ? JSON.stringify({ reason: body.reason ?? "" }) : undefined,
  });
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
