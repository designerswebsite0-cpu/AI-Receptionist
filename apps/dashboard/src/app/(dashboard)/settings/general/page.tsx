import { GeneralSettingsForm } from "@/components/settings/general-settings-form";
import { fetchFromApi } from "@/lib/server-api";

export default async function GeneralSettingsPage() {
  const response = await fetchFromApi("/api/v1/resort/settings");
  const payload = await response.json();

  if (!response.ok) {
    return <p className="text-sm text-red-600">{payload?.error?.message ?? "Could not load resort settings."}</p>;
  }

  return <GeneralSettingsForm initialSettings={payload.data} />;
}
