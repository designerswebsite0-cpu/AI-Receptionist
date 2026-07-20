import Link from "next/link";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi } from "@/lib/server-api";

type SourceOut = {
  id: string;
  source_id: string | null;
  title: string;
  source_type: string;
  visibility: string;
  source_priority: string;
  status: string;
  approval_status: string;
  processing_status: string;
  retrieval_enabled: boolean;
  created_at: string;
};

type SourceListResponse = { items: SourceOut[]; total: number; offset: number; limit: number };

export default async function KnowledgeSourcesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const search = params.search ?? "";
  const visibility = params.visibility ?? "";
  const status = params.status ?? "";

  const query = new URLSearchParams();
  if (search) query.set("search", search);
  if (visibility) query.set("visibility", visibility);
  if (status) query.set("status", status);
  query.set("page_size", "50");

  const response = await fetchFromApi(`/api/v1/knowledge/sources?${query.toString()}`);
  const payload = await response.json();
  const data: SourceListResponse = response.ok ? payload.data : { items: [], total: 0, offset: 0, limit: 50 };

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-charcoal">Knowledge Base</h1>
        <div className="flex gap-2 text-sm">
          <Link href="/knowledge/website" className="rounded-md border border-sand px-4 py-2 font-medium text-charcoal hover:bg-sand/40">
            Crawl website
          </Link>
          <Link href="/knowledge/search" className="rounded-md border border-sand px-4 py-2 font-medium text-charcoal hover:bg-sand/40">
            Search playground
          </Link>
          <Link href="/knowledge/jobs" className="rounded-md border border-sand px-4 py-2 font-medium text-charcoal hover:bg-sand/40">
            Ingestion jobs
          </Link>
          <Link href="/knowledge/upload" className="rounded-md bg-primary px-4 py-2 font-medium text-ivory hover:bg-primary-dark">
            Upload source
          </Link>
        </div>
      </div>

      <form className="mb-4 flex gap-3 text-sm" method="GET">
        <input
          type="text"
          name="search"
          defaultValue={search}
          placeholder="Search title or source ID…"
          className="w-64 rounded-md border border-sand px-3 py-1.5"
        />
        <select name="visibility" defaultValue={visibility} className="rounded-md border border-sand px-3 py-1.5">
          <option value="">All visibility</option>
          <option value="guest">guest</option>
          <option value="staff">staff</option>
          <option value="internal">internal</option>
          <option value="archive">archive</option>
          <option value="template">template</option>
        </select>
        <select name="status" defaultValue={status} className="rounded-md border border-sand px-3 py-1.5">
          <option value="">All statuses</option>
          <option value="draft">draft</option>
          <option value="active">active</option>
          <option value="superseded">superseded</option>
          <option value="archived">archived</option>
          <option value="rejected">rejected</option>
        </select>
        <button type="submit" className="rounded-md border border-sand px-3 py-1.5 hover:bg-sand/40">
          Filter
        </button>
      </form>

      {!response.ok && (
        <p className="text-sm text-red-600">{payload?.error?.message ?? "Could not load knowledge sources."}</p>
      )}

      {response.ok && data.items.length === 0 && (
        <p className="text-sm text-charcoal/50">No knowledge sources match these filters yet.</p>
      )}

      {response.ok && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-sand bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-sand bg-sand/20 text-left text-xs uppercase text-charcoal/50">
              <tr>
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2">Visibility</th>
                <th className="px-4 py-2">Priority</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Approval</th>
                <th className="px-4 py-2">Processing</th>
                <th className="px-4 py-2">Retrieval</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((source) => (
                <tr key={source.id} className="border-b border-sand/50 last:border-0 hover:bg-sand/10">
                  <td className="px-4 py-2">
                    <Link href={`/knowledge/${source.id}`} className="font-medium text-charcoal hover:underline">
                      {source.title}
                    </Link>
                    {source.source_id && <span className="ml-2 text-xs text-charcoal/40">{source.source_id}</span>}
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge value={source.visibility} />
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge value={source.source_priority} />
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge value={source.status} />
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge value={source.approval_status} />
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge value={source.processing_status} />
                  </td>
                  <td className="px-4 py-2 text-xs">{source.retrieval_enabled ? "✅ live" : "— not live"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {response.ok && (
        <p className="mt-3 text-xs text-charcoal/40">
          Showing {data.items.length} of {data.total} sources
        </p>
      )}
    </div>
  );
}
