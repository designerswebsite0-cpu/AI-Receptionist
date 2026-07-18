"use client";

import { useState } from "react";

type CrawlRunOut = {
  id: string;
  run_status: string;
  pages_discovered: number;
  pages_crawled: number;
  pages_changed: number;
  pages_failed: number;
  crawl_summary: Array<{ url: string; canonical_url: string; http_status: number; error: string | null }>;
};

export function WebsiteCrawlForm() {
  const [sourceId, setSourceId] = useState("WEB-RKPR-001");
  const [name, setName] = useState("RKPR Resort Official Website");
  const [baseUrl, setBaseUrl] = useState("https://rkpr-website.vercel.app");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CrawlRunOut | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setResult(null);

    const response = await fetch("/api/knowledge/website/crawl", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_id: sourceId,
        name,
        base_url: baseUrl,
        sitemap_url: `${baseUrl.replace(/\/$/, "")}/sitemap.xml`,
        robots_url: `${baseUrl.replace(/\/$/, "")}/robots.txt`,
        allowed_path_prefixes: [
          "/stay", "/compare-rooms", "/dining", "/spa-wellness", "/experiences", "/amenities",
          "/offers", "/events", "/transfers", "/location", "/nearby", "/policies", "/payments",
          "/directory", "/accessibility", "/families", "/safety", "/faq", "/contact",
        ],
        explicit_allow: ["/"],
        excluded_path_prefixes: ["/api", "/dev", "/_next"],
      }),
    });
    const payload = await response.json();
    setSubmitting(false);

    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Crawl failed");
      return;
    }
    setResult(payload.data as CrawlRunOut);
  }

  return (
    <div>
      <form onSubmit={handleSubmit} className="mb-6 space-y-4 rounded-lg border border-gray-200 bg-white p-6">
        <label className="block text-sm font-medium">
          Source ID
          <input
            value={sourceId}
            onChange={(e) => setSourceId(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
          />
        </label>
        <label className="block text-sm font-medium">
          Site name
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
          />
        </label>
        <label className="block text-sm font-medium">
          Base URL
          <input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
          />
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {submitting ? "Crawling…" : "Run crawl now"}
        </button>
      </form>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {result && (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="mb-3 text-sm">
            <StatusSummary result={result} />
          </p>
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="border-b border-gray-200 text-left uppercase text-gray-500">
                <tr>
                  <th className="py-1 pr-3">URL</th>
                  <th className="py-1 pr-3">Status</th>
                  <th className="py-1 pr-3">Error</th>
                </tr>
              </thead>
              <tbody>
                {result.crawl_summary.map((page) => (
                  <tr key={page.url} className="border-b border-gray-100 last:border-0">
                    <td className="py-1 pr-3">{page.canonical_url}</td>
                    <td className="py-1 pr-3">{page.http_status}</td>
                    <td className="py-1 pr-3 text-red-600">{page.error ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusSummary({ result }: { result: CrawlRunOut }) {
  return (
    <>
      {result.run_status} — {result.pages_discovered} discovered, {result.pages_crawled} crawled,{" "}
      {result.pages_changed} changed, {result.pages_failed} failed
    </>
  );
}
