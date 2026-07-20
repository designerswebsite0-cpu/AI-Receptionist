import Link from "next/link";
import { Star, Users } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { fetchFromApi } from "@/lib/server-api";
import type { CustomerListItem } from "@/components/customers/types";

export default async function CustomersPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const search = params.search ?? "";
  const tag = params.tag ?? "";

  const query = new URLSearchParams();
  if (search) query.set("search", search);
  if (tag) query.set("tag", tag);
  query.set("page_size", "50");

  const response = await fetchFromApi(`/api/v1/customers?${query.toString()}`);
  const payload = await response.json();
  const customers: CustomerListItem[] = response.ok ? payload.data.items : [];
  const total = response.ok ? payload.data.meta.total : 0;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-charcoal">Customer 360</h1>
        <p className="text-sm text-charcoal/50">{total} guests on record</p>
      </div>

      <form className="mb-4 flex gap-3 text-sm" method="GET">
        <input
          type="text"
          name="search"
          defaultValue={search}
          placeholder="Search name, phone, or email…"
          className="w-72 rounded-md border border-sand px-3 py-1.5"
        />
        <input
          type="text"
          name="tag"
          defaultValue={tag}
          placeholder="Filter by tag (e.g. vip)"
          className="w-48 rounded-md border border-sand px-3 py-1.5"
        />
        <button type="submit" className="rounded-md border border-sand px-3 py-1.5 hover:bg-sand/40">
          Filter
        </button>
      </form>

      {customers.length === 0 ? (
        <EmptyState icon={Users} title="No guests match" description="Try a different search or clear the filters." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-sand bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-sand bg-sand/20 text-left text-xs uppercase text-charcoal/50">
              <tr>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Contact</th>
                <th className="px-4 py-2">Tags</th>
                <th className="px-4 py-2">Conversations</th>
                <th className="px-4 py-2">Last interaction</th>
              </tr>
            </thead>
            <tbody>
              {customers.map((c) => (
                <tr key={c.id} className="border-b border-sand/50 last:border-0 hover:bg-sand/10">
                  <td className="px-4 py-2">
                    <Link href={`/customers/${c.id}`} className="flex items-center gap-1.5 font-medium text-charcoal hover:underline">
                      {c.is_vip && <Star size={12} className="fill-accent text-accent" />}
                      {c.full_name || `Guest ${c.id.slice(0, 8)}`}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-charcoal/60">{c.primary_contact?.value ?? "—"}</td>
                  <td className="px-4 py-2">
                    <div className="flex flex-wrap gap-1">
                      {c.tags.map((t) => (
                        <span key={t} className="rounded-full bg-sand/60 px-2 py-0.5 text-[11px] text-charcoal/70">
                          {t}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-2 text-charcoal/60">{c.conversation_count}</td>
                  <td className="px-4 py-2 text-xs text-charcoal/40">
                    {c.last_interaction_at ? new Date(c.last_interaction_at).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
