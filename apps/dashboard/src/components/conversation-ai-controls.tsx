"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function ConversationAiControls({ conversationId, status }: { conversationId: string; status: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [showHandoffForm, setShowHandoffForm] = useState(false);

  async function forceHandoff() {
    setPending(true);
    setError(null);
    const response = await fetch(`/api/orchestration/conversations/${conversationId}/handoff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason, department: "front_desk", priority: "normal" }),
    });
    const payload = await response.json();
    setPending(false);
    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Could not hand off this conversation");
      return;
    }
    setShowHandoffForm(false);
    setReason("");
    router.refresh();
  }

  async function release() {
    setPending(true);
    setError(null);
    const response = await fetch(`/api/orchestration/conversations/${conversationId}/release`, { method: "POST" });
    const payload = await response.json();
    setPending(false);
    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Could not release this conversation back to the AI");
      return;
    }
    router.refresh();
  }

  const isEscalated = status === "escalated" || status === "human_handling";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {!isEscalated && (
          <button
            onClick={() => setShowHandoffForm((v) => !v)}
            disabled={pending}
            className="rounded-md border border-orange-300 px-3 py-1.5 text-sm font-medium text-orange-700 disabled:opacity-50"
          >
            Hand off to staff
          </button>
        )}
        {isEscalated && (
          <button
            onClick={release}
            disabled={pending}
            className="rounded-md bg-gray-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {pending ? "Releasing…" : "Release back to AI"}
          </button>
        )}
      </div>

      {showHandoffForm && (
        <div className="flex gap-2">
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason for handoff"
            className="w-80 rounded-md border border-gray-300 px-3 py-1.5 text-sm"
          />
          <button
            onClick={forceHandoff}
            disabled={pending || !reason.trim()}
            className="rounded-md bg-orange-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {pending ? "Handing off…" : "Confirm handoff"}
          </button>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
