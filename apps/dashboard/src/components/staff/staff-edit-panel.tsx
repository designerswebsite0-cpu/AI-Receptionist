"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export function StaffEditPanel({
  userId,
  initialFullName,
  initialRole,
  initialStatus,
}: {
  userId: string;
  initialFullName: string | null;
  initialRole: string;
  initialStatus: string;
}) {
  const router = useRouter();
  const [fullName, setFullName] = useState(initialFullName ?? "");
  const [role, setRole] = useState(initialRole);
  const [status, setStatus] = useState(initialStatus);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    const response = await fetch(`/api/users/${userId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name: fullName || null, role, status }),
    });
    const payload = await response.json();
    setSaving(false);
    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Could not save changes.");
      return;
    }
    router.refresh();
  }

  return (
    <form onSubmit={handleSave} className="space-y-3">
      <div>
        <label className="mb-1 block text-xs font-medium text-charcoal/60">Display name</label>
        <input
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
        />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-charcoal/60">Role (display only)</label>
        <input
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
        />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-charcoal/60">Status</label>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
        >
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <Button type="submit" size="sm" loading={saving}>
        Save changes
      </Button>
    </form>
  );
}
