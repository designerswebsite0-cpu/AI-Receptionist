import Link from "next/link";
import { redirect } from "next/navigation";
import { DashboardNav } from "@/components/dashboard-nav";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi, getServerAccessToken } from "@/lib/server-api";

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
  const token = await getServerAccessToken();
  if (!token) redirect("/login");

  const response = await fetchFromApi("/api/v1/conversations?page_size=50");
  const payload = await response.json();
  const conversations: ConversationOut[] = response.ok ? payload.data.items : [];

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <DashboardNav />

      <h1 className="mb-6 text-lg font-semibold">Conversations</h1>

      {conversations.length === 0 && <p className="text-sm text-gray-500">No conversations yet.</p>}

      {conversations.length > 0 && (
        <table className="w-full text-sm">
          <thead className="border-b border-gray-200 text-left text-xs uppercase text-gray-500">
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
              <tr key={conversation.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                <td className="py-1.5 pr-4">
                  <Link href={`/conversations/${conversation.id}`} className="text-blue-700 hover:underline">
                    {conversation.channel}
                  </Link>
                </td>
                <td className="py-1.5 pr-4">
                  <StatusBadge value={conversation.status} />
                </td>
                <td className="py-1.5 pr-4">
                  {conversation.current_state}
                  {conversation.flow_state && (
                    <span className="ml-1 text-xs text-gray-400">/ {conversation.flow_state}</span>
                  )}
                </td>
                <td className="py-1.5 pr-4">
                  <StatusBadge value={conversation.priority} />
                </td>
                <td className="py-1.5 pr-4 text-gray-500">
                  {conversation.last_message_at ? new Date(conversation.last_message_at).toLocaleString() : "—"}
                </td>
                <td className="py-1.5 pr-4 text-gray-500">
                  {conversation.human_active ? "Staff" : conversation.ai_active ? "AI" : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
