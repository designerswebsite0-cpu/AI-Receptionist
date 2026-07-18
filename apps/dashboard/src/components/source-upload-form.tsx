"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function SourceUploadForm() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [visibility, setVisibility] = useState("guest");
  const [sourcePriority, setSourcePriority] = useState("normal");
  const [category, setCategory] = useState("");
  const [authoritative, setAuthoritative] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose a file to upload.");
      return;
    }
    setSubmitting(true);
    setError(null);

    const formData = new FormData();
    formData.set("file", file);
    formData.set("title", title);
    formData.set("visibility", visibility);
    formData.set("source_priority", sourcePriority);
    formData.set("authoritative", String(authoritative));
    if (category) formData.set("category", category);

    const response = await fetch("/api/knowledge/sources/upload", { method: "POST", body: formData });
    const payload = await response.json();
    setSubmitting(false);

    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Upload failed");
      return;
    }
    router.push(`/knowledge/${payload.data.id}`);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-gray-200 bg-white p-6">
      <label className="block text-sm font-medium">
        File
        <input
          type="file"
          required
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="mt-1 block w-full text-sm"
        />
        <span className="mt-1 block text-xs text-gray-400">PDF, DOCX, XLSX, CSV, HTML, TXT, or image.</span>
      </label>

      <label className="block text-sm font-medium">
        Title
        <input
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Guest Policies 2026"
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
        />
      </label>

      <div className="grid grid-cols-2 gap-4">
        <label className="block text-sm font-medium">
          Visibility
          <select
            value={visibility}
            onChange={(e) => setVisibility(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="guest">guest</option>
            <option value="staff">staff</option>
            <option value="internal">internal</option>
          </select>
        </label>
        <label className="block text-sm font-medium">
          Priority
          <select
            value={sourcePriority}
            onChange={(e) => setSourcePriority(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="critical">critical</option>
            <option value="high">high</option>
            <option value="normal">normal</option>
            <option value="low">low</option>
          </select>
        </label>
      </div>

      <label className="block text-sm font-medium">
        Category (optional)
        <input
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          placeholder="e.g. policy, dining, spa"
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
        />
      </label>

      <label className="flex items-center gap-2 text-sm font-medium">
        <input type="checkbox" checked={authoritative} onChange={(e) => setAuthoritative(e.target.checked)} />
        Authoritative source (overrides conflicting content)
      </label>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {submitting ? "Uploading…" : "Upload and process"}
      </button>
      <p className="text-xs text-gray-400">
        This registers the source, uploads it to storage, extracts text, chunks it, and generates embeddings. It
        will still need approval and activation before it&apos;s eligible for retrieval.
      </p>
    </form>
  );
}
