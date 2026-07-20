import Link from "next/link";
import { UserCog } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi } from "@/lib/server-api";

type StaffUser = {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  status: string;
  last_login_at: string | null;
  assigned_conversation_count: number;
};

export default async function StaffPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const search = params.search ?? "";
  const status = params.status ?? "";

  const query = new URLSearchParams();
  if (search) query.set("search", search);
  if (status) query.set("status", status);
  query.set("page_size", "50");

  const response = await fetchFromApi(`/api/v1/users?${query.toString()}`);
  const payload = await response.json();
  const staff: StaffUser[] = response.ok ? payload.data.items : [];
  const total = response.ok ? payload.data.meta.total : 0;

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-charcoal">Staff Management</h1>
        <p className="text-sm text-charcoal/50">{total} staff accounts</p>
      </div>

      <form className="mb-4 flex gap-3 text-sm" method="GET">
        <input
          type="text"
          name="search"
          defaultValue={search}
          placeholder="Search name or email…"
          className="w-72 rounded-md border border-sand px-3 py-1.5"
        />
        <select name="status" defaultValue={status} className="rounded-md border border-sand px-3 py-1.5">
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
        <button type="submit" className="rounded-md border border-sand px-3 py-1.5 hover:bg-sand/40">
          Filter
        </button>
      </form>

      {staff.length === 0 ? (
        <EmptyState icon={UserCog} title="No staff match" description="Try a different search or clear the filters." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-sand bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-sand bg-sand/20 text-left text-xs uppercase text-charcoal/50">
              <tr>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Role</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Open conversations</th>
                <th className="px-4 py-2">Last login</th>
              </tr>
            </thead>
            <tbody>
              {staff.map((s) => (
                <tr key={s.id} className="border-b border-sand/50 last:border-0 hover:bg-sand/10">
                  <td className="px-4 py-2">
                    <Link href={`/staff/${s.id}`} className="font-medium text-charcoal hover:underline">
                      {s.full_name || s.email}
                    </Link>
                    <p className="text-xs text-charcoal/40">{s.email}</p>
                  </td>
                  <td className="px-4 py-2 text-charcoal/60">{s.role}</td>
                  <td className="px-4 py-2">
                    <StatusBadge value={s.status} />
                  </td>
                  <td className="px-4 py-2 text-charcoal/60">{s.assigned_conversation_count}</td>
                  <td className="px-4 py-2 text-xs text-charcoal/40">
                    {s.last_login_at ? new Date(s.last_login_at).toLocaleString() : "Never"}
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
