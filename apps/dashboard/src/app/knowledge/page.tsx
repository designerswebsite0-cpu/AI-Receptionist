import Link from "next/link";
import { redirect } from "next/navigation";
import { DashboardNav } from "@/components/dashboard-nav";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi, getServerAccessToken } from "@/lib/server-api";

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
  const token = await getServerAccessToken();
  if (!token) redirect("/login");

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
    <main className="mx-auto max-w-5xl px-4 py-10">
      <DashboardNav />
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold">Knowledge Sources</h1>
        <Link
          href="/knowledge/upload"
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
        >
          Upload source
        </Link>
      </div>

      <form className="mb-4 flex gap-3 text-sm" method="GET">
        <input
          type="text"
          name="search"
          defaultValue={search}
          placeholder="Search title or source ID…"
          className="w-64 rounded-md border border-gray-300 px-3 py-1.5"
        />
        <select name="visibility" defaultValue={visibility} className="rounded-md border border-gray-300 px-3 py-1.5">
          <option value="">All visibility</option>
          <option value="guest">guest</option>
          <option value="staff">staff</option>
          <option value="internal">internal</option>
          <option value="archive">archive</option>
          <option value="template">template</option>
        </select>
        <select name="status" defaultValue={status} className="rounded-md border border-gray-300 px-3 py-1.5">
          <option value="">All statuses</option>
          <option value="draft">draft</option>
          <option value="active">active</option>
          <option value="superseded">superseded</option>
          <option value="archived">archived</option>
          <option value="rejected">rejected</option>
        </select>
        <button type="submit" className="rounded-md border border-gray-300 px-3 py-1.5 hover:bg-gray-100">
          Filter
        </button>
      </form>

      {!response.ok && (
        <p className="text-sm text-red-600">{payload?.error?.message ?? "Could not load knowledge sources."}</p>
      )}

      {response.ok && data.items.length === 0 && (
        <p className="text-sm text-gray-500">No knowledge sources match these filters yet.</p>
      )}

      {response.ok && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-gray-200 bg-gray-50 text-left text-xs uppercase text-gray-500">
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
                <tr key={source.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-2">
                    <Link href={`/knowledge/${source.id}`} className="font-medium text-gray-900 hover:underline">
                      {source.title}
                    </Link>
                    {source.source_id && <span className="ml-2 text-xs text-gray-400">{source.source_id}</span>}
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
        <p className="mt-3 text-xs text-gray-400">
          Showing {data.items.length} of {data.total} sources
        </p>
      )}
    </main>
  );
}
