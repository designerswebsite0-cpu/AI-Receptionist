import { redirect } from "next/navigation";
import { DashboardNav } from "@/components/dashboard-nav";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi, getServerAccessToken } from "@/lib/server-api";

type IngestionJobOut = {
  id: string;
  job_type: string;
  job_status: string;
  source_id: string | null;
  progress_current: number;
  progress_total: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
};

type JobListResponse = { items: IngestionJobOut[]; total: number };

export default async function IngestionJobsPage() {
  const token = await getServerAccessToken();
  if (!token) redirect("/login");

  const response = await fetchFromApi("/api/v1/knowledge/jobs?page_size=50");
  const payload = await response.json();
  const data: JobListResponse = response.ok ? payload.data : { items: [], total: 0 };

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <DashboardNav />
      <h1 className="mb-6 text-lg font-semibold">Ingestion Jobs</h1>

      {!response.ok && <p className="text-sm text-red-600">{payload?.error?.message ?? "Could not load jobs."}</p>}

      {response.ok && data.items.length === 0 && (
        <p className="text-sm text-gray-500">No ingestion jobs recorded yet.</p>
      )}

      {response.ok && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-gray-200 bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-2">Type</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Progress</th>
                <th className="px-4 py-2">Error</th>
                <th className="px-4 py-2">Created</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((job) => (
                <tr key={job.id} className="border-b border-gray-100 last:border-0">
                  <td className="px-4 py-2">{job.job_type}</td>
                  <td className="px-4 py-2">
                    <StatusBadge value={job.job_status} />
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-500">
                    {job.progress_current}
                    {job.progress_total ? ` / ${job.progress_total}` : ""}
                  </td>
                  <td className="px-4 py-2 text-xs text-red-600">{job.error_message ?? "—"}</td>
                  <td className="px-4 py-2 text-xs text-gray-400">{new Date(job.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
