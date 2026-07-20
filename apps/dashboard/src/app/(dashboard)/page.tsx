import { DashboardOverview } from "@/components/analytics/dashboard-overview";
import { fetchFromApi } from "@/lib/server-api";

type ResortSettings = { resort_name: string; city: string | null; country: string | null };

export default async function DashboardHomePage() {
  const [resortResponse, analyticsResponse] = await Promise.all([
    fetchFromApi("/api/v1/resort/settings"),
    fetchFromApi("/api/v1/analytics/dashboard?range=7d"),
  ]);
  const resort: ResortSettings | null = resortResponse.ok ? (await resortResponse.json()).data : null;
  const analyticsPayload = await analyticsResponse.json();

  return (
    <div className="mx-auto max-w-5xl">
      {resort && (
        <div className="mb-6 rounded-lg border border-sand bg-white px-4 py-3">
          <p className="text-sm font-medium text-charcoal">Welcome to {resort.resort_name}</p>
          {(resort.city || resort.country) && (
            <p className="text-xs text-charcoal/50">{[resort.city, resort.country].filter(Boolean).join(", ")}</p>
          )}
        </div>
      )}
      {analyticsResponse.ok ? (
        <DashboardOverview initialData={analyticsPayload.data} />
      ) : (
        <p className="text-sm text-red-600">{analyticsPayload?.error?.message ?? "Could not load analytics."}</p>
      )}
    </div>
  );
}
