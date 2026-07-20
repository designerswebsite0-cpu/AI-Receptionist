import { fetchFromApi } from "@/lib/server-api";

type AuditLogItem = {
  id: string;
  actor_user_id: string | null;
  actor_name: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  ip_address: string | null;
  created_at: string;
};

export default async function AuditLogsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const search = params.search ?? "";
  const dateFrom = params.date_from ?? "";
  const dateTo = params.date_to ?? "";

  const query = new URLSearchParams();
  if (search) query.set("search", search);
  if (dateFrom) query.set("date_from", dateFrom);
  if (dateTo) query.set("date_to", dateTo);
  query.set("page_size", "50");

  const response = await fetchFromApi(`/api/v1/audit/logs?${query.toString()}`);
  const payload = await response.json();
  const items: AuditLogItem[] = response.ok ? payload.data.items : [];
  const total = response.ok ? payload.data.meta.total : 0;

  return (
    <div>
      <p className="mb-4 text-sm text-charcoal/50">{total} audit events recorded</p>

      <form className="mb-4 flex flex-wrap gap-3 text-sm" method="GET">
        <input
          type="text"
          name="search"
          defaultValue={search}
          placeholder="Search action or resource…"
          className="w-64 rounded-md border border-sand px-3 py-1.5"
        />
        <input type="date" name="date_from" defaultValue={dateFrom} className="rounded-md border border-sand px-3 py-1.5" />
        <input type="date" name="date_to" defaultValue={dateTo} className="rounded-md border border-sand px-3 py-1.5" />
        <button type="submit" className="rounded-md border border-sand px-3 py-1.5 hover:bg-sand/40">
          Filter
        </button>
      </form>

      {!response.ok && <p className="text-sm text-red-600">{payload?.error?.message ?? "Could not load audit logs."}</p>}

      {response.ok && items.length === 0 && <p className="text-sm text-charcoal/50">No audit events match this filter.</p>}

      {response.ok && items.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-sand bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-sand bg-sand/20 text-left text-xs uppercase text-charcoal/50">
              <tr>
                <th className="px-4 py-2">Actor</th>
                <th className="px-4 py-2">Action</th>
                <th className="px-4 py-2">Resource</th>
                <th className="px-4 py-2">IP</th>
                <th className="px-4 py-2">When</th>
              </tr>
            </thead>
            <tbody>
              {items.map((log) => (
                <tr key={log.id} className="border-b border-sand/50 last:border-0">
                  <td className="px-4 py-2 text-charcoal">{log.actor_name ?? "System / AI"}</td>
                  <td className="px-4 py-2 font-mono text-xs text-charcoal/70">{log.action}</td>
                  <td className="px-4 py-2 text-xs text-charcoal/50">
                    {log.resource_type}
                    {log.resource_id && <span className="text-charcoal/30"> · {log.resource_id.slice(0, 8)}</span>}
                  </td>
                  <td className="px-4 py-2 text-xs text-charcoal/40">{log.ip_address ?? "—"}</td>
                  <td className="px-4 py-2 text-xs text-charcoal/40">{new Date(log.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
