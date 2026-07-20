"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { NoteOut } from "./types";

export function NotesPanel({ customerId, initialNotes }: { customerId: string; initialNotes: NoteOut[] }) {
  const [notes, setNotes] = useState(initialNotes);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const note = draft.trim();
    if (!note || saving) return;
    setSaving(true);
    setError(null);

    const response = await fetch(`/api/customers/${customerId}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note }),
    });
    const payload = await response.json();
    setSaving(false);

    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Could not save that note.");
      return;
    }
    setNotes((prev) => [{ ...payload.data, author_user_id: null }, ...prev]);
    setDraft("");
  }

  return (
    <div>
      <form onSubmit={handleAdd} className="mb-3 flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add an internal note…"
          className="flex-1 rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
        />
        <Button type="submit" size="sm" loading={saving} disabled={!draft.trim()}>
          Add
        </Button>
      </form>
      {error && <p className="mb-2 text-xs text-red-600">{error}</p>}
      {notes.length === 0 && <p className="text-sm text-charcoal/40">No staff notes yet.</p>}
      <div className="space-y-2">
        {notes.map((n) => (
          <div key={n.id} className="rounded-md border border-sand/60 bg-sand/10 p-2 text-sm">
            <p className="text-charcoal">{n.note}</p>
            <p className="mt-1 text-[11px] text-charcoal/40">{new Date(n.created_at).toLocaleString()}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
