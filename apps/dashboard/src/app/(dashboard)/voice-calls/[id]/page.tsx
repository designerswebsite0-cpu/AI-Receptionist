import Link from "next/link";
import { CallActionsPanel } from "@/components/voice/call-actions-panel";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi } from "@/lib/server-api";

type VoiceCall = {
  id: string;
  conversation_id: string;
  customer_name: string | null;
  twilio_call_sid: string | null;
  from_number: string | null;
  to_number: string | null;
  direction: string;
  status: string;
  outcome: string | null;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  ai_active: boolean | null;
  human_active: boolean | null;
  created_at: string;
};

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "Ongoing";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

export default async function VoiceCallDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const response = await fetchFromApi(`/api/v1/voice/calls/${id}`);

  if (response.status === 404) {
    return (
      <div className="mx-auto max-w-2xl">
        <p className="text-sm text-red-600">Voice call not found.</p>
      </div>
    );
  }

  const call: VoiceCall = (await response.json()).data;

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <Link href="/voice-calls" className="text-xs font-medium text-accent hover:underline">
          ← Back to voice calls
        </Link>
        <h1 className="mt-1 text-lg font-semibold text-charcoal">
          {call.customer_name || call.from_number || `Caller ${call.id.slice(0, 8)}`}
        </h1>
        <p className="text-xs text-charcoal/40">Received {new Date(call.created_at).toLocaleString()}</p>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        <StatusBadge value={call.status} />
        {call.outcome && <StatusBadge value={call.outcome} />}
        {call.human_active && (
          <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800">
            Staff active
          </span>
        )}
      </div>

      <div className="mb-6 grid grid-cols-2 gap-4 rounded-lg border border-sand bg-white p-4 text-sm">
        <div>
          <p className="text-xs text-charcoal/40">From</p>
          <p className="text-charcoal">{call.from_number ?? "Unknown"}</p>
        </div>
        <div>
          <p className="text-xs text-charcoal/40">To</p>
          <p className="text-charcoal">{call.to_number ?? "Unknown"}</p>
        </div>
        <div>
          <p className="text-xs text-charcoal/40">Duration</p>
          <p className="text-charcoal">{formatDuration(call.duration_seconds)}</p>
        </div>
        <div>
          <p className="text-xs text-charcoal/40">Direction</p>
          <p className="text-charcoal capitalize">{call.direction}</p>
        </div>
        <Link
          href={`/conversations/${call.conversation_id}`}
          className="col-span-2 mt-1 inline-block text-xs font-medium text-accent hover:underline"
        >
          View full transcript &amp; customer history →
        </Link>
      </div>

      <div className="rounded-lg border border-sand bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-charcoal">Call actions</h2>
        <CallActionsPanel callId={call.id} status={call.status} />
      </div>
    </div>
  );
}
