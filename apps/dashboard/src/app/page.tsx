import { redirect } from "next/navigation";
import { CreateTenantForm } from "@/components/create-tenant-form";
import { HealthBadge } from "@/components/health-badge";
import { LogoutButton } from "@/components/logout-button";
import { fetchFromApi, getServerAccessToken } from "@/lib/server-api";

type Membership = { tenant_id: string; tenant_name: string; tenant_slug: string; role: string };
type MeResponse = { user_id: string; email: string; memberships: Membership[] };

export default async function DashboardHomePage() {
  const token = await getServerAccessToken();
  if (!token) {
    redirect("/login");
  }

  const response = await fetchFromApi("/api/v1/auth/me");
  if (response.status === 401) {
    redirect("/login");
  }

  const payload = await response.json();
  const me = payload.data as MeResponse;

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">AI Receptionist</h1>
          <p className="text-sm text-gray-500">{me.email}</p>
        </div>
        <div className="flex items-center gap-4">
          <HealthBadge />
          <LogoutButton />
        </div>
      </header>

      {me.memberships.length === 0 ? (
        <CreateTenantForm />
      ) : (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-gray-700">Your tenants</h2>
          {me.memberships.map((m) => (
            <div
              key={m.tenant_id}
              className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3"
            >
              <div>
                <p className="text-sm font-medium">{m.tenant_name}</p>
                <p className="text-xs text-gray-500">{m.tenant_slug}</p>
              </div>
              <span className="rounded-full bg-gray-100 px-2 py-1 text-xs font-medium capitalize">
                {m.role.replace("_", " ")}
              </span>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
