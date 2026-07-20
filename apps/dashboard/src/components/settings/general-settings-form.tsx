"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

type ResortSettings = {
  resort_name: string;
  phone: string | null;
  email: string | null;
  website_url: string | null;
  timezone: string;
  currency: string;
  default_language: string;
  check_in_time: string | null;
  check_out_time: string | null;
  settings_metadata: Record<string, unknown>;
};

export function GeneralSettingsForm({ initialSettings }: { initialSettings: ResortSettings }) {
  const router = useRouter();
  const meta = initialSettings.settings_metadata ?? {};

  const [resortName, setResortName] = useState(initialSettings.resort_name);
  const [phone, setPhone] = useState(initialSettings.phone ?? "");
  const [email, setEmail] = useState(initialSettings.email ?? "");
  const [websiteUrl, setWebsiteUrl] = useState(initialSettings.website_url ?? "");
  const [timezone, setTimezone] = useState(initialSettings.timezone);
  const [currency, setCurrency] = useState(initialSettings.currency);
  const [checkInTime, setCheckInTime] = useState(initialSettings.check_in_time ?? "");
  const [checkOutTime, setCheckOutTime] = useState(initialSettings.check_out_time ?? "");

  const [businessHours, setBusinessHours] = useState((meta.business_hours as string) ?? "24/7");
  const [supportedLanguages, setSupportedLanguages] = useState(
    Array.isArray(meta.supported_languages) ? (meta.supported_languages as string[]).join(", ") : "en",
  );
  const [chatAvailability, setChatAvailability] = useState((meta.chat_availability as string) ?? "24/7");
  const [humanHandoffHours, setHumanHandoffHours] = useState((meta.human_handoff_hours as string) ?? "");
  const [aiDisplayName, setAiDisplayName] = useState((meta.ai_display_name as string) ?? "");
  const [fallbackMessage, setFallbackMessage] = useState(
    (meta.fallback_message as string) ??
      "I'm sorry, I'm not able to help with that right now — a staff member will follow up shortly.",
  );
  const [emergencyContact, setEmergencyContact] = useState((meta.emergency_contact as string) ?? "");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);

    const response = await fetch("/api/resort/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resort_name: resortName,
        phone: phone || null,
        email: email || null,
        website_url: websiteUrl || null,
        timezone,
        currency,
        check_in_time: checkInTime || null,
        check_out_time: checkOutTime || null,
        settings_metadata: {
          ...meta,
          business_hours: businessHours,
          supported_languages: supportedLanguages.split(",").map((s) => s.trim()).filter(Boolean),
          chat_availability: chatAvailability,
          human_handoff_hours: humanHandoffHours,
          ai_display_name: aiDisplayName,
          fallback_message: fallbackMessage,
          emergency_contact: emergencyContact,
        },
      }),
    });
    const payload = await response.json();
    setSaving(false);
    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Could not save settings.");
      return;
    }
    setSaved(true);
    router.refresh();
  }

  return (
    <form onSubmit={handleSave} className="space-y-6">
      <div className="rounded-lg border border-sand bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-charcoal">Property details</h2>
        <div className="space-y-3">
          <label className="block text-sm">
            <span className="mb-1 block text-xs font-medium text-charcoal/60">Resort name</span>
            <input
              required
              value={resortName}
              onChange={(e) => setResortName(e.target.value)}
              className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-charcoal/60">Phone</span>
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-charcoal/60">Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
              />
            </label>
          </div>
          <label className="block text-sm">
            <span className="mb-1 block text-xs font-medium text-charcoal/60">Website</span>
            <input
              value={websiteUrl}
              onChange={(e) => setWebsiteUrl(e.target.value)}
              placeholder="https://"
              className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-charcoal/60">Timezone</span>
              <input
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-charcoal/60">Currency</span>
              <input
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
              />
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-charcoal/60">Check-in time</span>
              <input
                value={checkInTime}
                onChange={(e) => setCheckInTime(e.target.value)}
                className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-charcoal/60">Check-out time</span>
              <input
                value={checkOutTime}
                onChange={(e) => setCheckOutTime(e.target.value)}
                className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
              />
            </label>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-sand bg-white p-4">
        <h2 className="mb-1 text-sm font-semibold text-charcoal">AI receptionist behavior</h2>
        <p className="mb-3 text-xs text-charcoal/40">
          Stored in resort_settings.settings_metadata — read by the orchestration pipeline and website chat.
        </p>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-charcoal/60">AI display name</span>
              <input
                value={aiDisplayName}
                onChange={(e) => setAiDisplayName(e.target.value)}
                placeholder="e.g. Aria"
                className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-charcoal/60">Supported languages</span>
              <input
                value={supportedLanguages}
                onChange={(e) => setSupportedLanguages(e.target.value)}
                placeholder="en, es, fr"
                className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
              />
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-charcoal/60">Business hours</span>
              <input
                value={businessHours}
                onChange={(e) => setBusinessHours(e.target.value)}
                placeholder="24/7 or 8am-10pm"
                className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-charcoal/60">Chat availability</span>
              <input
                value={chatAvailability}
                onChange={(e) => setChatAvailability(e.target.value)}
                placeholder="24/7 or 8am-10pm"
                className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
              />
            </label>
          </div>
          <label className="block text-sm">
            <span className="mb-1 block text-xs font-medium text-charcoal/60">Human hand-off hours</span>
            <input
              value={humanHandoffHours}
              onChange={(e) => setHumanHandoffHours(e.target.value)}
              placeholder="When staff are available to take over from the AI"
              className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-xs font-medium text-charcoal/60">Emergency contact</span>
            <input
              value={emergencyContact}
              onChange={(e) => setEmergencyContact(e.target.value)}
              className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-xs font-medium text-charcoal/60">Fallback message</span>
            <textarea
              value={fallbackMessage}
              onChange={(e) => setFallbackMessage(e.target.value)}
              rows={3}
              className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
            />
          </label>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {saved && !error && <p className="text-sm text-green-700">Saved.</p>}
      <Button type="submit" loading={saving}>
        Save settings
      </Button>
    </form>
  );
}
