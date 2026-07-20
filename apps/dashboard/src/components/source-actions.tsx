"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function SourceActions({
  sourceId,
  approvalStatus,
  status,
  retrievalEnabled,
  sourceType,
}: {
  sourceId: string;
  approvalStatus: string;
  status: string;
  retrievalEnabled: boolean;
  sourceType: string;
}) {
  const router = useRouter();
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const canDelete = status !== "active" && !retrievalEnabled;

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

  async function runDelete() {
    setPending("delete");
    setError(null);
    const response = await fetch(`/api/knowledge/sources/${sourceId}`, { method: "DELETE" });
    const payload = await response.json();
    setPending(null);
    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Could not delete this source");
      return;
    }
    router.push("/knowledge");
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
        {sourceType === "document" && (
          <button
            onClick={() => runAction("reprocess")}
            disabled={pending !== null}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 disabled:opacity-50"
          >
            {pending === "reprocess" ? "Reprocessing…" : "Reprocess"}
          </button>
        )}
        {canDelete && (
          <button
            onClick={() => setShowDeleteConfirm((v) => !v)}
            disabled={pending !== null}
            className="rounded-md border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 disabled:opacity-50"
          >
            Delete
          </button>
        )}
      </div>

      {showDeleteConfirm && (
        <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 p-3">
          <p className="flex-1 text-sm text-red-700">
            Permanently delete this source and all its versions/chunks? This cannot be undone.
          </p>
          <button
            onClick={runDelete}
            disabled={pending !== null}
            className="rounded-md bg-red-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {pending === "delete" ? "Deleting…" : "Confirm delete"}
          </button>
          <button
            onClick={() => setShowDeleteConfirm(false)}
            disabled={pending !== null}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700"
          >
            Cancel
          </button>
        </div>
      )}

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
