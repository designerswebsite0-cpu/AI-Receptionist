import Link from "next/link";
import { Mail, Phone, Tag as TagIcon } from "lucide-react";
import { ConversationAiControls } from "@/components/conversation-ai-controls";
import { StatusBadge } from "@/components/status-badge";
import type { ConversationOut, CustomerOut } from "./types";

export function CustomerPanel({
  conversation,
  customer,
}: {
  conversation: ConversationOut;
  customer: CustomerOut | null;
}) {
  return (
    <div className="hidden h-full w-72 shrink-0 flex-col overflow-y-auto border-l border-sand/70 bg-white p-4 xl:flex">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-charcoal">
          {customer?.full_name || `Guest ${conversation.customer_id.slice(0, 8)}`}
        </h2>
        <Link href={`/customers/${conversation.customer_id}`} className="text-xs text-accent hover:underline">
          View full profile
        </Link>
      </div>

      {customer && customer.contacts.length > 0 && (
        <div className="mb-4 space-y-1">
          {customer.contacts.map((contact) => (
            <p key={contact.id} className="flex items-center gap-1.5 text-xs text-charcoal/60">
              {contact.contact_type === "email" ? <Mail size={12} /> : <Phone size={12} />}
              {contact.value}
            </p>
          ))}
        </div>
      )}

      {customer && customer.tags.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-1">
          {customer.tags.map((tag) => (
            <span
              key={tag}
              className="flex items-center gap-1 rounded-full bg-sand/60 px-2 py-0.5 text-[11px] text-charcoal/70"
            >
              <TagIcon size={10} /> {tag}
            </span>
          ))}
        </div>
      )}

      <div className="mb-4 space-y-1.5 border-t border-sand/70 pt-3">
        <p className="text-xs text-charcoal/40">Conversation</p>
        <div className="flex flex-wrap gap-1.5">
          <StatusBadge value={conversation.status} />
          <StatusBadge value={conversation.priority} />
        </div>
        <p className="text-xs text-charcoal/60">
          {conversation.assigned_agent_id ? "Assigned to a staff member" : "Unassigned"}
        </p>
      </div>

      <div className="border-t border-sand/70 pt-3">
        <p className="mb-2 text-xs text-charcoal/40">AI / staff control</p>
        <ConversationAiControls conversationId={conversation.id} status={conversation.status} />
      </div>
    </div>
  );
}
