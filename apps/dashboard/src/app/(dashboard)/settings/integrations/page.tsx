import { IntegrationsPanel } from "@/components/settings/integrations-panel";
import { fetchFromApi } from "@/lib/server-api";

export default async function IntegrationsSettingsPage() {
  const response = await fetchFromApi("/api/v1/health/integrations");
  const payload = await response.json();

  if (!response.ok) {
    return <p className="text-sm text-red-600">{payload?.error?.message ?? "Could not load integration status."}</p>;
  }

  return <IntegrationsPanel initialStatus={payload.data} />;
}
