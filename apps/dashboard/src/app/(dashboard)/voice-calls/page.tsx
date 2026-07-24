import Link from "next/link";
import { Phone } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi } from "@/lib/server-api";

type VoiceCall = {
  id: string;
  customer_name: string | null;
  from_number: string | null;
  to_number: string | null;
  status: string;
  outcome: string | null;
  duration_seconds: number | null;
  created_at: string;
};

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default async function VoiceCallsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const status = params.status ?? "";

  const query = new URLSearchParams();
  if (status) query.set("status", status);
  query.set("page_size", "50");

  const [listResponse, activeResponse] = await Promise.all([
    fetchFromApi(`/api/v1/voice/calls?${query.toString()}`),
    fetchFromApi("/api/v1/voice/calls/active"),
  ]);
  const listPayload = await listResponse.json();
  const activePayload = await activeResponse.json();
  const calls: VoiceCall[] = listResponse.ok ? listPayload.data.items : [];
  const total = listResponse.ok ? listPayload.data.meta.total : 0;
  const activeCalls: VoiceCall[] = activeResponse.ok ? activePayload.data.items : [];

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-charcoal">Voice Calls</h1>
        <p className="text-sm text-charcoal/50">{total} inbound calls — {activeCalls.length} active right now.</p>
      </div>

      {activeCalls.length > 0 && (
        <div className="mb-6 rounded-lg border border-accent/40 bg-accent/5 p-4">
          <h2 className="mb-2 text-sm font-semibold text-charcoal">Active now</h2>
          <div className="space-y-2">
            {activeCalls.map((c) => (
              <Link
                key={c.id}
                href={`/voice-calls/${c.id}`}
                className="flex items-center justify-between rounded-md border border-sand bg-white px-3 py-2 text-sm hover:bg-sand/10"
              >
                <span className="font-medium text-charcoal">{c.customer_name || c.from_number || "Unknown caller"}</span>
                <StatusBadge value={c.status} />
              </Link>
            ))}
          </div>
        </div>
      )}

      <form className="mb-4 flex gap-3 text-sm" method="GET">
        <select name="status" defaultValue={status} className="rounded-md border border-sand px-3 py-1.5">
          <option value="">All statuses</option>
          <option value="ringing">Ringing</option>
          <option value="in_progress">In progress</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="no_answer">No answer</option>
        </select>
        <button type="submit" className="rounded-md border border-sand px-3 py-1.5 hover:bg-sand/40">
          Filter
        </button>
      </form>

      {calls.length === 0 ? (
        <EmptyState icon={Phone} title="No voice calls yet" description="Inbound calls will appear here once the voice channel is live." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-sand bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-sand bg-sand/20 text-left text-xs uppercase text-charcoal/50">
              <tr>
                <th className="px-4 py-2">Caller</th>
                <th className="px-4 py-2">From</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Outcome</th>
                <th className="px-4 py-2">Duration</th>
                <th className="px-4 py-2">Received</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((c) => (
                <tr key={c.id} className="border-b border-sand/50 last:border-0 hover:bg-sand/10">
                  <td className="px-4 py-2">
                    <Link href={`/voice-calls/${c.id}`} className="font-medium text-charcoal hover:underline">
                      {c.customer_name || `Caller ${c.id.slice(0, 8)}`}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-charcoal/60">{c.from_number ?? "—"}</td>
                  <td className="px-4 py-2">
                    <StatusBadge value={c.status} />
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge value={c.outcome} />
                  </td>
                  <td className="px-4 py-2 text-charcoal/60">{formatDuration(c.duration_seconds)}</td>
                  <td className="px-4 py-2 text-xs text-charcoal/40">{new Date(c.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
