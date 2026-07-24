"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export function RoomBookingReviewPanel({
  bookingId,
  status,
  guestName,
  guestPhone,
  checkInDate,
  checkOutDate,
  numGuests,
  breakfastIncluded,
  specialPreferences,
  staffNotes,
}: {
  bookingId: string;
  status: string;
  guestName: string;
  guestPhone: string;
  checkInDate: string;
  checkOutDate: string;
  numGuests: number;
  breakfastIncluded: boolean;
  specialPreferences: string | null;
  staffNotes: string | null;
}) {
  const router = useRouter();
  const [form, setForm] = useState({
    guest_name: guestName,
    guest_phone: guestPhone,
    check_in_date: checkInDate,
    check_out_date: checkOutDate,
    num_guests: numGuests,
    breakfast_included: breakfastIncluded,
    special_preferences: specialPreferences ?? "",
    staff_notes: staffNotes ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isPending = status === "pending_review";

  async function handleSaveCorrections(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    const response = await fetch(`/api/bookings/${bookingId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    const payload = await response.json();
    setSaving(false);
    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Could not save corrections.");
      return;
    }
    router.refresh();
  }

  async function handleConfirm() {
    if (!window.confirm(`Confirm this booking and send an SMS to ${form.guest_phone}?`)) return;
    setConfirming(true);
    setError(null);
    const response = await fetch(`/api/bookings/${bookingId}/confirm`, { method: "POST" });
    const payload = await response.json();
    setConfirming(false);
    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Could not confirm booking.");
      return;
    }
    router.refresh();
  }

  async function handleReject() {
    if (!window.confirm("Reject this booking? The guest will not be notified automatically.")) return;
    setRejecting(true);
    setError(null);
    const response = await fetch(`/api/bookings/${bookingId}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ staff_notes: form.staff_notes || null }),
    });
    const payload = await response.json();
    setRejecting(false);
    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Could not reject booking.");
      return;
    }
    router.refresh();
  }

  if (!isPending) {
    return (
      <p className="text-sm text-charcoal/60">
        This booking is <span className="font-medium">{status}</span> — no further action available.
      </p>
    );
  }

  return (
    <form onSubmit={handleSaveCorrections} className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-charcoal/60">Guest name</label>
          <input
            value={form.guest_name}
            onChange={(e) => setForm({ ...form, guest_name: e.target.value })}
            className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-charcoal/60">Guest phone</label>
          <input
            value={form.guest_phone}
            onChange={(e) => setForm({ ...form, guest_phone: e.target.value })}
            className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-charcoal/60">Check-in date</label>
          <input
            type="date"
            value={form.check_in_date}
            onChange={(e) => setForm({ ...form, check_in_date: e.target.value })}
            className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-charcoal/60">Check-out date</label>
          <input
            type="date"
            value={form.check_out_date}
            onChange={(e) => setForm({ ...form, check_out_date: e.target.value })}
            className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-charcoal/60">Guests</label>
          <input
            type="number"
            min={1}
            value={form.num_guests}
            onChange={(e) => setForm({ ...form, num_guests: Number(e.target.value) })}
            className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
          />
        </div>
        <div className="flex items-end">
          <label className="flex items-center gap-2 text-sm text-charcoal">
            <input
              type="checkbox"
              checked={form.breakfast_included}
              onChange={(e) => setForm({ ...form, breakfast_included: e.target.checked })}
            />
            Breakfast included
          </label>
        </div>
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-charcoal/60">Special preferences</label>
        <textarea
          value={form.special_preferences}
          onChange={(e) => setForm({ ...form, special_preferences: e.target.value })}
          rows={2}
          className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
        />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-charcoal/60">Staff notes</label>
        <textarea
          value={form.staff_notes}
          onChange={(e) => setForm({ ...form, staff_notes: e.target.value })}
          rows={2}
          placeholder="e.g. Called guest to verify phone number"
          className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
        />
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex flex-wrap gap-2 pt-2">
        <Button type="submit" variant="secondary" size="sm" loading={saving}>
          Save corrections
        </Button>
        <Button type="button" variant="primary" size="sm" loading={confirming} onClick={handleConfirm}>
          Confirm &amp; send SMS
        </Button>
        <Button type="button" variant="danger" size="sm" loading={rejecting} onClick={handleReject}>
          Reject
        </Button>
      </div>
    </form>
  );
}
