import { redirect } from "next/navigation";
import { DashboardNav } from "@/components/dashboard-nav";
import { SourceActions } from "@/components/source-actions";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi, getServerAccessToken } from "@/lib/server-api";

type SourceOut = {
  id: string;
  source_id: string | null;
  title: string;
  description: string | null;
  source_type: string;
  category: string | null;
  visibility: string;
  source_priority: string;
  authoritative: boolean;
  status: string;
  approval_status: string;
  processing_status: string;
  malware_scan_status: string;
  ocr_required: boolean;
  retrieval_enabled: boolean;
  effective_date: string | null;
  expiry_date: string | null;
  created_at: string;
};

type SourceVersionOut = {
  id: string;
  version_number: number;
  page_count: number | null;
  word_count: number | null;
  extraction_method: string | null;
  ocr_used: boolean;
  processing_status: string;
  is_current: boolean;
  created_at: string;
};

export default async function SourceDetailPage({ params }: { params: Promise<{ sourceId: string }> }) {
  const token = await getServerAccessToken();
  if (!token) redirect("/login");

  const { sourceId } = await params;
  const [sourceResponse, versionsResponse] = await Promise.all([
    fetchFromApi(`/api/v1/knowledge/sources/${sourceId}`),
    fetchFromApi(`/api/v1/knowledge/sources/${sourceId}/versions`),
  ]);

  if (sourceResponse.status === 404) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <DashboardNav />
        <p className="text-sm text-red-600">Knowledge source not found.</p>
      </main>
    );
  }

  const sourcePayload = await sourceResponse.json();
  const source: SourceOut = sourcePayload.data;
  const versionsPayload = await versionsResponse.json();
  const versions: SourceVersionOut[] = versionsResponse.ok ? versionsPayload.data : [];

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <DashboardNav />

      <div className="mb-6">
        <h1 className="text-lg font-semibold">{source.title}</h1>
        {source.source_id && <p className="text-xs text-gray-400">{source.source_id}</p>}
        {source.description && <p className="mt-1 text-sm text-gray-600">{source.description}</p>}
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        <StatusBadge value={source.visibility} />
        <StatusBadge value={source.source_priority} />
        <StatusBadge value={source.status} />
        <StatusBadge value={source.approval_status} />
        <StatusBadge value={source.processing_status} />
        <StatusBadge value={source.malware_scan_status} />
        {source.authoritative && <StatusBadge value="authoritative" />}
      </div>

      <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold">Governance actions</h2>
        <SourceActions sourceId={source.id} approvalStatus={source.approval_status} />
        <p className="mt-3 text-xs text-gray-400">
          {source.retrieval_enabled
            ? "This source is live and eligible for retrieval."
            : "Activation requires: approved + processing completed + malware scan clean/unscanned_dev_only."}
        </p>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold">Versions</h2>
        {versions.length === 0 && <p className="text-sm text-gray-500">No versions recorded yet.</p>}
        {versions.length > 0 && (
          <table className="w-full text-sm">
            <thead className="border-b border-gray-200 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="py-1.5 pr-4">Version</th>
                <th className="py-1.5 pr-4">Pages</th>
                <th className="py-1.5 pr-4">Words</th>
                <th className="py-1.5 pr-4">Extraction</th>
                <th className="py-1.5 pr-4">Status</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((version) => (
                <tr key={version.id} className="border-b border-gray-100 last:border-0">
                  <td className="py-1.5 pr-4">
                    v{version.version_number}
                    {version.is_current && <span className="ml-1 text-xs text-gray-400">(current)</span>}
                  </td>
                  <td className="py-1.5 pr-4">{version.page_count ?? "—"}</td>
                  <td className="py-1.5 pr-4">{version.word_count ?? "—"}</td>
                  <td className="py-1.5 pr-4">
                    {version.extraction_method ?? "—"}
                    {version.ocr_used && <span className="ml-1 text-xs text-gray-400">(OCR)</span>}
                  </td>
                  <td className="py-1.5 pr-4">
                    <StatusBadge value={version.processing_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}
