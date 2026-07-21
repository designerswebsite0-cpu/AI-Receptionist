import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi } from "@/lib/server-api";

type SystemStatus = {
  overall: string;
  checks: Record<string, string>;
  domains: {
    knowledge_base: { active_sources: number; failed: number; needs_review: number; pending: number };
    conversations: { escalated_needing_attention: number; orphaned_not_handled_by_ai_or_staff: number };
    bookings: { pending_review: number };
    notifications: { unread: number };
    recent_errors_24h: { area: string; count: number }[];
  } | null;
};

const CHECK_LABELS: Record<string, string> = {
  database: "Database",
  embedding_provider: "Embedding provider",
  llm_primary_openai: "Primary LLM (OpenAI)",
  llm_fallback_groq: "Fallback LLM (Groq)",
  redis: "Redis",
};

function Tile({ label, value, warn, href }: { label: string; value: number; warn?: boolean; href?: string }) {
  const content = (
    <div className={`rounded-lg border p-4 ${warn && value > 0 ? "border-red-200 bg-red-50" : "border-sand bg-white"}`}>
      <p className="text-xs text-charcoal/40">{label}</p>
      <p className={`text-xl font-semibold ${warn && value > 0 ? "text-red-700" : "text-charcoal"}`}>{value}</p>
    </div>
  );
  return href ? <Link href={href}>{content}</Link> : content;
}

export default async function SystemMonitoringPage() {
  const response = await fetchFromApi("/api/v1/health/system");
  const payload = await response.json();

  if (!response.ok) {
    return <p className="text-sm text-red-600">{payload?.error?.message ?? "Could not load system status."}</p>;
  }

  const status: SystemStatus = payload.data;
  const d = status.domains;

  return (
    <div>
      <div className="mb-4 rounded-lg border border-sand bg-white p-4">
        <p className="mb-1 text-xs text-charcoal/40">Overall status</p>
        <StatusBadge value={status.overall} />
      </div>

      <div className="mb-4 overflow-hidden rounded-lg border border-sand bg-white">
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

      {d && (
        <>
          <h2 className="mb-2 text-sm font-semibold text-charcoal">Needs attention</h2>
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Tile label="Escalated conversations" value={d.conversations.escalated_needing_attention} warn href="/conversations" />
            <Tile
              label="Orphaned conversations"
              value={d.conversations.orphaned_not_handled_by_ai_or_staff}
              warn
              href="/conversations"
            />
            <Tile label="Pending booking reviews" value={d.bookings.pending_review} href="/bookings" />
            <Tile label="Unread notifications" value={d.notifications.unread} href="/notifications" />
          </div>

          <h2 className="mb-2 text-sm font-semibold text-charcoal">Knowledge base</h2>
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Tile label="Active & live" value={d.knowledge_base.active_sources} href="/knowledge" />
            <Tile label="Failed ingestion" value={d.knowledge_base.failed} warn href="/knowledge" />
            <Tile label="Needs review" value={d.knowledge_base.needs_review} href="/knowledge" />
            <Tile label="Pending ingestion" value={d.knowledge_base.pending} href="/knowledge" />
          </div>

          <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-charcoal">
            <AlertTriangle size={14} /> Errors in the last 24 hours
          </h2>
          {d.recent_errors_24h.length === 0 ? (
            <p className="text-sm text-charcoal/40">No failure events logged in the last 24 hours.</p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-sand bg-white">
              <table className="w-full text-sm">
                <thead className="border-b border-sand bg-sand/20 text-left text-xs uppercase text-charcoal/50">
                  <tr>
                    <th className="px-4 py-2">Area</th>
                    <th className="px-4 py-2">Count</th>
                  </tr>
                </thead>
                <tbody>
                  {d.recent_errors_24h.map((row) => (
                    <tr key={row.area} className="border-b border-sand/50 last:border-0">
                      <td className="px-4 py-2 text-charcoal">{row.area.replace(/_/g, " ")}</td>
                      <td className="px-4 py-2 text-red-700">{row.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <p className="mt-3 text-xs text-charcoal/40">
        Aggregated status only — no stack traces, credentials, or environment variables are ever shown here.
      </p>
    </div>
  );
}
