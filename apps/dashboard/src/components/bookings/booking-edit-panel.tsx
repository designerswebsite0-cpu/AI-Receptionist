"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

type StaffOption = { id: string; full_name: string | null; email: string };

export function BookingEditPanel({
  bookingId,
  initialStatus,
  initialBookingStatus,
  initialStaffNotes,
  initialAssignedAgentId,
}: {
  bookingId: string;
  initialStatus: string;
  initialBookingStatus: string | null;
  initialStaffNotes: string | null;
  initialAssignedAgentId: string | null;
}) {
  const router = useRouter();
  const [status, setStatus] = useState(initialStatus);
  const [bookingStatus, setBookingStatus] = useState(initialBookingStatus ?? "pending_review");
  const [staffNotes, setStaffNotes] = useState(initialStaffNotes ?? "");
  const [assignedAgentId, setAssignedAgentId] = useState(initialAssignedAgentId ?? "");
  const [staff, setStaff] = useState<StaffOption[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/users?status=active&page_size=100")
      .then((r) => r.json())
      .then((payload) => {
        if (payload.success) setStaff(payload.data.items);
      });
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    const response = await fetch(`/api/bookings/${bookingId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status,
        booking_status: bookingStatus,
        staff_notes: staffNotes,
        assigned_agent_id: assignedAgentId || null,
      }),
    });
    const payload = await response.json();
    setSaving(false);
    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Could not save changes.");
      return;
    }
    router.refresh();
  }

  return (
    <form onSubmit={handleSave} className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-charcoal/60">Queue status</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
          >
            <option value="open">Open</option>
            <option value="in_progress">In progress</option>
            <option value="resolved">Resolved</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-charcoal/60">Booking status</label>
          <select
            value={bookingStatus}
            onChange={(e) => setBookingStatus(e.target.value)}
            className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
          >
            <option value="pending_review">Pending review</option>
            <option value="confirmed">Confirmed</option>
            <option value="rejected">Rejected</option>
            <option value="completed">Completed</option>
          </select>
        </div>
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-charcoal/60">Assigned to</label>
        <select
          value={assignedAgentId}
          onChange={(e) => setAssignedAgentId(e.target.value)}
          className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
        >
          <option value="">Unassigned</option>
          {staff.map((s) => (
            <option key={s.id} value={s.id}>
              {s.full_name || s.email}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-charcoal/60">Staff notes</label>
        <textarea
          value={staffNotes}
          onChange={(e) => setStaffNotes(e.target.value)}
          rows={3}
          placeholder="e.g. Called guest, confirmed by phone on 20 Jul"
          className="w-full rounded-md border border-sand px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
        />
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <Button type="submit" size="sm" loading={saving}>
        Save changes
      </Button>
    </form>
  );
}
