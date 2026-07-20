import { Inbox } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";

export default function ConversationsIndexPage() {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <EmptyState icon={Inbox} title="Select a conversation" description="Choose a conversation from the list to view the thread." />
    </div>
  );
}
