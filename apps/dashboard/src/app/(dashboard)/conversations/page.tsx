import Link from "next/link";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi } from "@/lib/server-api";

type ConversationOut = {
  id: string;
  channel: string;
  status: string;
  current_state: string;
  flow_state: string | null;
  priority: string;
  last_message_at: string | null;
  ai_active: boolean;
  human_active: boolean;
};

export default async function ConversationsListPage() {
  const response = await fetchFromApi("/api/v1/conversations?page_size=50");
  const payload = await response.json();
  const conversations: ConversationOut[] = response.ok ? payload.data.items : [];

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-6 text-lg font-semibold text-charcoal">Conversations</h1>

      {conversations.length === 0 && <p className="text-sm text-charcoal/50">No conversations yet.</p>}

      {conversations.length > 0 && (
        <table className="w-full text-sm">
          <thead className="border-b border-sand text-left text-xs uppercase text-charcoal/50">
            <tr>
              <th className="py-1.5 pr-4">Channel</th>
              <th className="py-1.5 pr-4">Status</th>
              <th className="py-1.5 pr-4">Dialogue state</th>
              <th className="py-1.5 pr-4">Priority</th>
              <th className="py-1.5 pr-4">Last message</th>
              <th className="py-1.5 pr-4">Handled by</th>
            </tr>
          </thead>
          <tbody>
            {conversations.map((conversation) => (
              <tr key={conversation.id} className="border-b border-sand/50 last:border-0 hover:bg-sand/20">
                <td className="py-1.5 pr-4">
                  <Link href={`/conversations/${conversation.id}`} className="text-primary hover:underline">
                    {conversation.channel}
                  </Link>
                </td>
                <td className="py-1.5 pr-4">
                  <StatusBadge value={conversation.status} />
                </td>
                <td className="py-1.5 pr-4">
                  {conversation.current_state}
                  {conversation.flow_state && (
                    <span className="ml-1 text-xs text-charcoal/40">/ {conversation.flow_state}</span>
                  )}
                </td>
                <td className="py-1.5 pr-4">
                  <StatusBadge value={conversation.priority} />
                </td>
                <td className="py-1.5 pr-4 text-charcoal/50">
                  {conversation.last_message_at ? new Date(conversation.last_message_at).toLocaleString() : "—"}
                </td>
                <td className="py-1.5 pr-4 text-charcoal/50">
                  {conversation.human_active ? "Staff" : conversation.ai_active ? "AI" : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
