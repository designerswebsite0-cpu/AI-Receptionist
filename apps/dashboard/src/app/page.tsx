import { redirect } from "next/navigation";
import { HealthBadge } from "@/components/health-badge";
import { LogoutButton } from "@/components/logout-button";
import { ResortSetupForm } from "@/components/resort-setup-form";
import { fetchFromApi, getServerAccessToken } from "@/lib/server-api";

type MeResponse = { user_id: string; email: string; resort_configured: boolean };
type ResortSettings = { resort_name: string; city: string | null; country: string | null };

export default async function DashboardHomePage() {
  const token = await getServerAccessToken();
  if (!token) {
    redirect("/login");
  }

  const meResponse = await fetchFromApi("/api/v1/auth/me");
  if (meResponse.status === 401) {
    redirect("/login");
  }
  const me = (await meResponse.json()).data as MeResponse;

  let resort: ResortSettings | null = null;
  if (me.resort_configured) {
    const resortResponse = await fetchFromApi("/api/v1/resort/settings");
    if (resortResponse.ok) {
      resort = (await resortResponse.json()).data as ResortSettings;
    }
  }

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

      {!resort ? (
        <ResortSetupForm />
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white px-4 py-3">
          <p className="text-sm font-medium">Welcome to {resort.resort_name}</p>
          {(resort.city || resort.country) && (
            <p className="text-xs text-gray-500">{[resort.city, resort.country].filter(Boolean).join(", ")}</p>
          )}
        </div>
      )}
    </main>
  );
}
