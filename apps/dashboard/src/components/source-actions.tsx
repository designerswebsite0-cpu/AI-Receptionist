"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function SourceActions({ sourceId, approvalStatus }: { sourceId: string; approvalStatus: string }) {
  const router = useRouter();
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);

  async function runAction(action: string, reason?: string) {
    setPending(action);
    setError(null);
    const response = await fetch(`/api/knowledge/sources/${sourceId}/actions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, reason }),
    });
    const payload = await response.json();
    setPending(null);
    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? `Could not ${action} this source`);
      return;
    }
    setShowRejectForm(false);
    router.refresh();
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {approvalStatus !== "approved" && (
          <button
            onClick={() => runAction("approve")}
            disabled={pending !== null}
            className="rounded-md bg-green-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {pending === "approve" ? "Approving…" : "Approve"}
          </button>
        )}
        <button
          onClick={() => setShowRejectForm((v) => !v)}
          disabled={pending !== null}
          className="rounded-md border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 disabled:opacity-50"
        >
          Reject
        </button>
        <button
          onClick={() => runAction("activate")}
          disabled={pending !== null}
          className="rounded-md bg-gray-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {pending === "activate" ? "Activating…" : "Activate (make retrievable)"}
        </button>
        <button
          onClick={() => runAction("archive")}
          disabled={pending !== null}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 disabled:opacity-50"
        >
          {pending === "archive" ? "Archiving…" : "Archive"}
        </button>
      </div>

      {showRejectForm && (
        <div className="flex gap-2">
          <input
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="Reason for rejection"
            className="w-80 rounded-md border border-gray-300 px-3 py-1.5 text-sm"
          />
          <button
            onClick={() => runAction("reject", rejectReason)}
            disabled={pending !== null || !rejectReason.trim()}
            className="rounded-md bg-red-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            Confirm reject
          </button>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
