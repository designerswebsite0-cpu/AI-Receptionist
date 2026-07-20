import { ConversationThread } from "@/components/inbox/thread";
import { CustomerPanel } from "@/components/inbox/customer-panel";
import type { ConversationOut, CustomerOut, MessageOut } from "@/components/inbox/types";
import { fetchFromApi } from "@/lib/server-api";

export default async function ConversationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [conversationRes, messagesRes] = await Promise.all([
    fetchFromApi(`/api/v1/conversations/${id}`),
    fetchFromApi(`/api/v1/conversations/${id}/messages?page_size=200`),
  ]);

  if (conversationRes.status === 404) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-red-600">Conversation not found.</p>
      </div>
    );
  }

  const conversation: ConversationOut = (await conversationRes.json()).data;
  const messagesPayload = await messagesRes.json();
  const messages: MessageOut[] = messagesRes.ok ? messagesPayload.data.items : [];

  const customerRes = await fetchFromApi(`/api/v1/customers/${conversation.customer_id}`);
  const customer: CustomerOut | null = customerRes.ok ? (await customerRes.json()).data : null;

  return (
    <div className="flex h-full">
      <div className="min-w-0 flex-1">
        <ConversationThread
          conversationId={conversation.id}
          initialMessages={messages}
          aiActive={conversation.ai_active}
          humanActive={conversation.human_active}
        />
      </div>
      <CustomerPanel conversation={conversation} customer={customer} />
    </div>
  );
}
