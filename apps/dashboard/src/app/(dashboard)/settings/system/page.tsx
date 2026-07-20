import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi } from "@/lib/server-api";

type SystemStatus = {
  overall: string;
  checks: Record<string, string>;
};

const CHECK_LABELS: Record<string, string> = {
  database: "Database",
  embedding_provider: "Embedding provider",
  llm_primary_openai: "Primary LLM (OpenAI)",
  llm_fallback_groq: "Fallback LLM (Groq)",
  redis: "Redis",
};

export default async function SystemMonitoringPage() {
  const response = await fetchFromApi("/api/v1/health/system");
  const payload = await response.json();

  if (!response.ok) {
    return <p className="text-sm text-red-600">{payload?.error?.message ?? "Could not load system status."}</p>;
  }

  const status: SystemStatus = payload.data;

  return (
    <div>
      <div className="mb-4 rounded-lg border border-sand bg-white p-4">
        <p className="mb-1 text-xs text-charcoal/40">Overall status</p>
        <StatusBadge value={status.overall} />
      </div>

      <div className="overflow-hidden rounded-lg border border-sand bg-white">
        <table className="w-full text-sm">
          <thead className="border-b border-sand bg-sand/20 text-left text-xs uppercase text-charcoal/50">
            <tr>
              <th className="px-4 py-2">Component</th>
              <th className="px-4 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(status.checks).map(([key, value]) => (
              <tr key={key} className="border-b border-sand/50 last:border-0">
                <td className="px-4 py-2 text-charcoal">{CHECK_LABELS[key] ?? key}</td>
                <td className="px-4 py-2">
                  <StatusBadge value={value} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-charcoal/40">
        Aggregated status only — no stack traces, credentials, or environment variables are ever shown here.
      </p>
    </div>
  );
}
