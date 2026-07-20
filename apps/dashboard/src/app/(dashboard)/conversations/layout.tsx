import { InboxListPanel } from "@/components/inbox/list-panel";
import { fetchFromApi } from "@/lib/server-api";
import type { ConversationOut } from "@/components/inbox/types";

export default async function InboxLayout({ children }: { children: React.ReactNode }) {
  const response = await fetchFromApi("/api/v1/conversations?page_size=50");
  const payload = await response.json();
  const conversations: ConversationOut[] = response.ok ? payload.data.items : [];

  return (
    <div className="-m-4 flex h-[calc(100vh-3.5rem)] sm:-m-6">
      <InboxListPanel initialConversations={conversations} />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
