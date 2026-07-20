import Link from "next/link";
import { Mail, Phone, Star } from "lucide-react";
import { NotesPanel } from "@/components/customers/notes-panel";
import { TagsPanel } from "@/components/customers/tags-panel";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi } from "@/lib/server-api";
import type { CustomerDetail, NoteOut } from "@/components/customers/types";

interface ConversationSummary {
  id: string;
  channel: string;
  status: string;
  last_message_at: string | null;
  started_at: string;
}

function aiInferredEntries(customer: CustomerDetail): { field: string; value: unknown }[] {
  const inferred = customer.resort_preferences?.ai_inferred as Record<string, { value: unknown }> | undefined;
  if (!inferred || typeof inferred !== "object") return [];
  return Object.entries(inferred).map(([field, entry]) => ({ field, value: entry?.value }));
}

export default async function CustomerDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [customerRes, notesRes, conversationsRes] = await Promise.all([
    fetchFromApi(`/api/v1/customers/${id}`),
    fetchFromApi(`/api/v1/customers/${id}/notes`),
    fetchFromApi(`/api/v1/conversations?customer_id=${id}&page_size=20`),
  ]);

  if (customerRes.status === 404) {
    return (
      <div className="mx-auto max-w-3xl">
        <p className="text-sm text-red-600">Guest not found.</p>
      </div>
    );
  }

  const customer: CustomerDetail = (await customerRes.json()).data;
  const notes: NoteOut[] = notesRes.ok ? await notesRes.json().then((p) => p.data) : [];
  const conversations: ConversationSummary[] = conversationsRes.ok
    ? (await conversationsRes.json()).data.items
    : [];
  const preferences = aiInferredEntries(customer);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-center gap-2">
        {customer.is_vip && <Star size={18} className="fill-accent text-accent" />}
        <h1 className="text-lg font-semibold text-charcoal">
          {customer.full_name || `Guest ${customer.id.slice(0, 8)}`}
        </h1>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <div className="space-y-6 md:col-span-1">
          <div className="rounded-lg border border-sand bg-white p-4">
            <h2 className="mb-2 text-sm font-semibold text-charcoal">Contact</h2>
            {customer.contacts.length === 0 && <p className="text-sm text-charcoal/40">No contact details on file.</p>}
            <div className="space-y-1">
              {customer.contacts.map((c) => (
                <p key={c.id} className="flex items-center gap-1.5 text-sm text-charcoal/70">
                  {c.contact_type === "email" ? <Mail size={13} /> : <Phone size={13} />}
                  {c.value}
                  {c.verified && <StatusBadge value="verified" />}
                </p>
              ))}
            </div>
            <p className="mt-2 text-xs text-charcoal/40">Preferred language: {customer.preferred_language}</p>
            {customer.loyalty_reference && (
              <p className="text-xs text-charcoal/40">Loyalty ref: {customer.loyalty_reference}</p>
            )}
            <p className="text-xs text-charcoal/40">Guest since {new Date(customer.created_at).toLocaleDateString()}</p>
          </div>

          <div className="rounded-lg border border-sand bg-white p-4">
            <h2 className="mb-2 text-sm font-semibold text-charcoal">Tags</h2>
            <TagsPanel customerId={customer.id} initialTags={customer.tags} />
          </div>

          <div className="rounded-lg border border-sand bg-white p-4">
            <h2 className="mb-2 text-sm font-semibold text-charcoal">AI-noted preferences</h2>
            <p className="mb-2 text-[11px] text-charcoal/40">Unconfirmed — from past AI conversations, not verified by staff.</p>
            {preferences.length === 0 && <p className="text-sm text-charcoal/40">Nothing noted yet.</p>}
            <div className="space-y-1">
              {preferences.map((p) => (
                <p key={p.field} className="text-sm text-charcoal/70">
                  <span className="text-charcoal/40">{p.field.replace(/_/g, " ")}:</span> {String(p.value)}
                </p>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-6 md:col-span-2">
          <div className="rounded-lg border border-sand bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-charcoal">Conversation history</h2>
            {conversations.length === 0 && <p className="text-sm text-charcoal/40">No conversations yet.</p>}
            <div className="space-y-2">
              {conversations.map((c) => (
                <Link
                  key={c.id}
                  href={`/conversations/${c.id}`}
                  className="flex items-center justify-between rounded-md border border-sand/60 px-3 py-2 text-sm hover:bg-sand/10"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs uppercase text-charcoal/40">{c.channel}</span>
                    <StatusBadge value={c.status} />
                  </div>
                  <span className="text-xs text-charcoal/40">
                    {c.last_message_at ? new Date(c.last_message_at).toLocaleString() : "—"}
                  </span>
                </Link>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-sand bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-charcoal">Staff notes</h2>
            <NotesPanel customerId={customer.id} initialNotes={notes} />
          </div>
        </div>
      </div>
    </div>
  );
}
