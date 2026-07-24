"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

export function ClearWebchatSessionsButton() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    if (
      !window.confirm(
        "Clear all website chat sessions? Every guest with an open chat window will need to start a new session. Conversation history is not affected.",
      )
    ) {
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    const response = await fetch("/api/webchat/admin/sessions/clear", { method: "POST" });
    const payload = await response.json();
    setLoading(false);
    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Could not clear sessions.");
      return;
    }
    setResult(`Cleared ${payload.data.sessions_cleared} active session(s).`);
  }

  return (
    <div className="rounded-lg border border-sand bg-white p-4">
      <h2 className="mb-1 text-sm font-semibold text-charcoal">Website chat sessions</h2>
      <p className="mb-3 text-xs text-charcoal/50">
        Manually invalidate every active website-chat session cookie — a maintenance action, never run automatically.
        Guest conversation history is not deleted.
      </p>
      <Button variant="secondary" size="sm" loading={loading} onClick={handleClick}>
        Clear all sessions
      </Button>
      {result && <p className="mt-2 text-xs text-green-700">{result}</p>}
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}
