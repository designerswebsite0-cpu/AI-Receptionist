"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function CreateTenantForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    const response = await fetch("/api/tenants", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, slug }),
    });
    const payload = await response.json();

    setSubmitting(false);
    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Could not create tenant");
      return;
    }
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-lg border border-gray-200 bg-white p-6">
      <h2 className="text-sm font-semibold">Create your first tenant</h2>
      <p className="text-sm text-gray-500">You&apos;ll be added as the owner automatically.</p>

      <label className="block text-sm font-medium">
        Business name
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
        />
      </label>

      <label className="block text-sm font-medium">
        Slug
        <input
          required
          value={slug}
          onChange={(e) => setSlug(e.target.value.toLowerCase())}
          placeholder="acme-dental"
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
        />
      </label>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {submitting ? "Creating…" : "Create tenant"}
      </button>
    </form>
  );
}
