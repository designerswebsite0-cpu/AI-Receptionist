"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const STATUSES = ["new", "reviewed", "actioned", "dismissed"];

export function FeedbackStatusSelect({ feedbackId, initialStatus }: { feedbackId: string; initialStatus: string }) {
  const router = useRouter();
  const [status, setStatus] = useState(initialStatus);
  const [saving, setSaving] = useState(false);

  async function handleChange(next: string) {
    setStatus(next);
    setSaving(true);
    await fetch(`/api/feedback/${feedbackId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: next }),
    });
    setSaving(false);
    router.refresh();
  }

  return (
    <select
      value={status}
      disabled={saving}
      onChange={(e) => handleChange(e.target.value)}
      className="rounded-md border border-sand px-2 py-1 text-xs disabled:opacity-50"
    >
      {STATUSES.map((s) => (
        <option key={s} value={s}>
          {s}
        </option>
      ))}
    </select>
  );
}
