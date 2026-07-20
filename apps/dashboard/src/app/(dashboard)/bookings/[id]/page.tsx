import Link from "next/link";
import { BookingEditPanel } from "@/components/bookings/booking-edit-panel";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi } from "@/lib/server-api";

type BookingRequest = {
  id: string;
  conversation_id: string;
  customer_name: string | null;
  status: string;
  booking_status: string | null;
  check_in_date: string | null;
  num_nights: number | null;
  adults: number | null;
  room_category: string | null;
  staff_notes: string | null;
  assigned_agent_id: string | null;
  created_by: string;
  created_at: string;
};

export default async function BookingDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const response = await fetchFromApi(`/api/v1/bookings/${id}`);

  if (response.status === 404) {
    return (
      <div className="mx-auto max-w-2xl">
        <p className="text-sm text-red-600">Booking enquiry not found.</p>
      </div>
    );
  }

  const booking: BookingRequest = (await response.json()).data;

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <Link href="/bookings" className="text-xs font-medium text-accent hover:underline">
          ← Back to bookings
        </Link>
        <h1 className="mt-1 text-lg font-semibold text-charcoal">
          {booking.customer_name || `Guest ${booking.id.slice(0, 8)}`} — booking enquiry
        </h1>
        <p className="text-xs text-charcoal/40">
          Received {new Date(booking.created_at).toLocaleString()} via {booking.created_by === "ai" ? "AI receptionist" : "staff"}
        </p>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        <StatusBadge value={booking.status} />
        <StatusBadge value={booking.booking_status ?? "pending_review"} />
      </div>

      <div className="mb-6 rounded-lg border border-sand bg-white p-4">
        <p className="mb-3 text-xs text-charcoal/40">
          A guest enquiry only — this is not a confirmed reservation and no live room availability was checked.
        </p>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-xs text-charcoal/40">Check-in date</p>
            <p className="text-charcoal">{booking.check_in_date ?? "Not specified"}</p>
          </div>
          <div>
            <p className="text-xs text-charcoal/40">Nights</p>
            <p className="text-charcoal">{booking.num_nights ?? "Not specified"}</p>
          </div>
          <div>
            <p className="text-xs text-charcoal/40">Adults</p>
            <p className="text-charcoal">{booking.adults ?? "Not specified"}</p>
          </div>
          <div>
            <p className="text-xs text-charcoal/40">Room category</p>
            <p className="text-charcoal">{booking.room_category ?? "Not specified"}</p>
          </div>
        </div>
        <Link
          href={`/conversations/${booking.conversation_id}`}
          className="mt-3 inline-block text-xs font-medium text-accent hover:underline"
        >
          View source conversation →
        </Link>
      </div>

      <div className="rounded-lg border border-sand bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-charcoal">Triage</h2>
        <BookingEditPanel
          bookingId={booking.id}
          initialStatus={booking.status}
          initialBookingStatus={booking.booking_status}
          initialStaffNotes={booking.staff_notes}
          initialAssignedAgentId={booking.assigned_agent_id}
        />
      </div>
    </div>
  );
}
