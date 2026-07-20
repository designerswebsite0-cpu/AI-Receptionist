import { SourceActions } from "@/components/source-actions";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi } from "@/lib/server-api";

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
  const { sourceId } = await params;
  const [sourceResponse, versionsResponse] = await Promise.all([
    fetchFromApi(`/api/v1/knowledge/sources/${sourceId}`),
    fetchFromApi(`/api/v1/knowledge/sources/${sourceId}/versions`),
  ]);

  if (sourceResponse.status === 404) {
    return (
      <div className="mx-auto max-w-3xl">
        <p className="text-sm text-red-600">Knowledge source not found.</p>
      </div>
    );
  }

  const sourcePayload = await sourceResponse.json();
  const source: SourceOut = sourcePayload.data;
  const versionsPayload = await versionsResponse.json();
  const versions: SourceVersionOut[] = versionsResponse.ok ? versionsPayload.data : [];

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-charcoal">{source.title}</h1>
        {source.source_id && <p className="text-xs text-charcoal/40">{source.source_id}</p>}
        {source.description && <p className="mt-1 text-sm text-charcoal/60">{source.description}</p>}
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

      <div className="mb-6 rounded-lg border border-sand bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-charcoal">Governance actions</h2>
        <SourceActions sourceId={source.id} approvalStatus={source.approval_status} />
        <p className="mt-3 text-xs text-charcoal/40">
          {source.retrieval_enabled
            ? "This source is live and eligible for retrieval."
            : "Activation requires: approved + processing completed + malware scan clean/unscanned_dev_only."}
        </p>
      </div>

      <div className="rounded-lg border border-sand bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-charcoal">Versions</h2>
        {versions.length === 0 && <p className="text-sm text-charcoal/50">No versions recorded yet.</p>}
        {versions.length > 0 && (
          <table className="w-full text-sm">
            <thead className="border-b border-sand text-left text-xs uppercase text-charcoal/50">
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
                <tr key={version.id} className="border-b border-sand/50 last:border-0">
                  <td className="py-1.5 pr-4">
                    v{version.version_number}
                    {version.is_current && <span className="ml-1 text-xs text-charcoal/40">(current)</span>}
                  </td>
                  <td className="py-1.5 pr-4">{version.page_count ?? "—"}</td>
                  <td className="py-1.5 pr-4">{version.word_count ?? "—"}</td>
                  <td className="py-1.5 pr-4">
                    {version.extraction_method ?? "—"}
                    {version.ocr_used && <span className="ml-1 text-xs text-charcoal/40">(OCR)</span>}
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
    </div>
  );
}
