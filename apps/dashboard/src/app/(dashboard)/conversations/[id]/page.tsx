import { ConversationAiControls } from "@/components/conversation-ai-controls";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi } from "@/lib/server-api";

type ConversationOut = {
  id: string;
  customer_id: string;
  channel: string;
  status: string;
  current_state: string;
  flow_state: string | null;
  priority: string;
  ai_active: boolean;
  human_active: boolean;
  summary: string | null;
};

type MessageOut = {
  id: string;
  direction: string;
  sender_type: string;
  content_text: string | null;
  created_at: string;
};

type ConversationStateOut = {
  last_intent: string | null;
  last_intent_confidence: number | null;
};

type OrchestrationTurnOut = {
  id: string;
  detected_intent: string | null;
  intent_confidence: number | null;
  flow_state: string | null;
  tool_name: string | null;
  tool_status: string | null;
  handoff_required: boolean;
  handoff_reason: string | null;
  provider_used: string | null;
  model_used: string | null;
  latency_ms: number | null;
  error_code: string | null;
  created_at: string;
};

export default async function ConversationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [conversationRes, messagesRes, stateRes, turnsRes] = await Promise.all([
    fetchFromApi(`/api/v1/conversations/${id}`),
    fetchFromApi(`/api/v1/conversations/${id}/messages?page_size=100`),
    fetchFromApi(`/api/v1/orchestration/conversations/${id}/state`),
    fetchFromApi(`/api/v1/orchestration/conversations/${id}/turns?page_size=20`),
  ]);

  if (conversationRes.status === 404) {
    return (
      <div className="mx-auto max-w-5xl">
        <p className="text-sm text-red-600">Conversation not found.</p>
      </div>
    );
  }

  const conversation: ConversationOut = (await conversationRes.json()).data;
  const messagesPayload = await messagesRes.json();
  const messages: MessageOut[] = messagesRes.ok ? messagesPayload.data.items : [];
  const statePayload = await stateRes.json();
  const state: ConversationStateOut | null = stateRes.ok ? statePayload.data : null;
  const turnsPayload = await turnsRes.json();
  const turns: OrchestrationTurnOut[] = turnsRes.ok ? turnsPayload.data.items : [];

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold text-charcoal">Conversation ({conversation.channel})</h1>
          <div className="mt-2 flex flex-wrap gap-2">
            <StatusBadge value={conversation.status} />
            <StatusBadge value={conversation.priority} />
            <span className="text-xs text-charcoal/40">
              {conversation.current_state}
              {conversation.flow_state && ` / ${conversation.flow_state}`}
            </span>
          </div>
        </div>
        <ConversationAiControls conversationId={conversation.id} status={conversation.status} />
      </div>

      {conversation.summary && (
        <div className="mb-6 rounded-lg border border-sand bg-white p-4">
          <h2 className="mb-1 text-sm font-semibold text-charcoal">AI-generated summary</h2>
          <p className="text-sm text-charcoal/60">{conversation.summary}</p>
        </div>
      )}

      <div className="mb-6 grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="rounded-lg border border-sand bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-charcoal">Messages</h2>
          {messages.length === 0 && <p className="text-sm text-charcoal/50">No messages yet.</p>}
          <div className="max-h-96 space-y-2 overflow-y-auto">
            {messages.map((message) => (
              <div key={message.id} className={message.direction === "inbound" ? "text-left" : "text-right"}>
                <span
                  className={`inline-block max-w-[85%] rounded-lg px-3 py-1.5 text-sm ${
                    message.sender_type === "customer"
                      ? "bg-sand/40 text-charcoal"
                      : message.sender_type === "ai"
                        ? "bg-primary/10 text-primary"
                        : "bg-accent/10 text-accent"
                  }`}
                >
                  <span className="mr-1 text-xs font-medium uppercase text-charcoal/40">{message.sender_type}</span>
                  {message.content_text ?? "(no text content)"}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-sand bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-charcoal">AI decision trace (orchestration turns)</h2>
          {state?.last_intent && (
            <p className="mb-3 text-xs text-charcoal/50">
              Last detected intent: <span className="font-medium">{state.last_intent}</span>{" "}
              {state.last_intent_confidence !== null && `(${Math.round(state.last_intent_confidence * 100)}%)`}
            </p>
          )}
          {turns.length === 0 && <p className="text-sm text-charcoal/50">No AI turns recorded yet.</p>}
          <div className="max-h-96 space-y-3 overflow-y-auto">
            {turns.map((turn) => (
              <div key={turn.id} className="border-b border-sand/60 pb-2 text-xs last:border-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-charcoal">{turn.detected_intent ?? "unknown"}</span>
                  {turn.intent_confidence !== null && (
                    <span className="text-charcoal/40">{Math.round(turn.intent_confidence * 100)}%</span>
                  )}
                  {turn.handoff_required && <StatusBadge value="escalated" />}
                  {turn.tool_name && <StatusBadge value={turn.tool_status ?? "pending"} />}
                  {turn.error_code && <StatusBadge value="failed" />}
                </div>
                {turn.tool_name && <p className="mt-1 text-charcoal/50">tool: {turn.tool_name}</p>}
                {turn.handoff_reason && <p className="mt-1 text-charcoal/50">handoff reason: {turn.handoff_reason}</p>}
                <p className="mt-1 text-charcoal/40">
                  {turn.provider_used ? `${turn.provider_used}/${turn.model_used}` : "no LLM call"}
                  {turn.latency_ms !== null && ` · ${turn.latency_ms}ms`}
                  {" · "}
                  {new Date(turn.created_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
