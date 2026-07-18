"use client";

import { useState } from "react";

type CitationOut = {
  chunk_id: string;
  content: string;
  chunk_type: string;
  section_title: string | null;
  source_title: string;
  source_external_id: string | null;
  source_priority: string;
  authoritative: boolean;
  source_url: string | null;
  score: number;
};

type SearchResponse = {
  query: string;
  query_classification: string;
  results: CitationOut[];
  latency_ms: number;
};

export function SearchPlayground() {
  const [query, setQuery] = useState("");
  const [guestOnly, setGuestOnly] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SearchResponse | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);

    const response = await fetch("/api/knowledge/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, guest_only: guestOnly, limit: 10 }),
    });
    const payload = await response.json();
    setLoading(false);

    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Search failed");
      setResult(null);
      return;
    }
    setResult(payload.data as SearchResponse);
  }

  return (
    <div>
      <form onSubmit={handleSubmit} className="mb-6 flex gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="What time does the pool close?"
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
        />
        <label className="flex items-center gap-2 whitespace-nowrap text-sm">
          <input type="checkbox" checked={guestOnly} onChange={(e) => setGuestOnly(e.target.checked)} />
          Guest-only
        </label>
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {result && (
        <div>
          <p className="mb-3 text-xs text-gray-400">
            Classified as <span className="font-medium">{result.query_classification}</span> · {result.latency_ms}ms
            · {result.results.length} results
          </p>
          <div className="space-y-3">
            {result.results.map((citation) => (
              <div key={citation.chunk_id} className="rounded-lg border border-gray-200 bg-white p-4">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-medium">{citation.source_title}</span>
                  <span className="text-xs text-gray-400">score {citation.score.toFixed(3)}</span>
                </div>
                {citation.section_title && <p className="mb-1 text-xs text-gray-500">{citation.section_title}</p>}
                <p className="whitespace-pre-wrap text-sm text-gray-700">{citation.content}</p>
                <div className="mt-2 flex gap-2 text-xs text-gray-400">
                  <span>{citation.chunk_type}</span>
                  <span>·</span>
                  <span>{citation.source_priority}</span>
                  {citation.authoritative && (
                    <>
                      <span>·</span>
                      <span>authoritative</span>
                    </>
                  )}
                </div>
              </div>
            ))}
            {result.results.length === 0 && (
              <p className="text-sm text-gray-500">No matching guest-eligible content found.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
