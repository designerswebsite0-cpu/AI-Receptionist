import { fetchFromApi } from "@/lib/server-api";

type ResortSettings = { resort_name: string; city: string | null; country: string | null };

export default async function DashboardHomePage() {
  const resortResponse = await fetchFromApi("/api/v1/resort/settings");
  const resort: ResortSettings | null = resortResponse.ok ? (await resortResponse.json()).data : null;

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
      <p className="text-sm text-charcoal/50">
        Live metrics, analytics and activity feed land here in Phase X&apos;s Dashboard &amp; Analytics stage.
      </p>
    </div>
  );
}
