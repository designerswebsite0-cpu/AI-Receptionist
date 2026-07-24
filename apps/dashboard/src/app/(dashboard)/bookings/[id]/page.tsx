import Link from "next/link";
import { RoomBookingReviewPanel } from "@/components/bookings/room-booking-review-panel";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi } from "@/lib/server-api";

type RoomBooking = {
  id: string;
  conversation_id: string | null;
  customer_name: string | null;
  room_type_name: string | null;
  check_in_date: string;
  check_out_date: string;
  num_guests: number;
  breakfast_included: boolean;
  guest_name: string;
  guest_phone: string;
  special_preferences: string | null;
  status: string;
  staff_notes: string | null;
  confirmation_sms_status: string | null;
  confirmation_sms_error: string | null;
  created_at: string;
};

export default async function BookingDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const response = await fetchFromApi(`/api/v1/bookings/${id}`);

  if (response.status === 404) {
    return (
      <div className="mx-auto max-w-2xl">
        <p className="text-sm text-red-600">Room booking not found.</p>
      </div>
    );
  }

  const booking: RoomBooking = (await response.json()).data;

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <Link href="/bookings" className="text-xs font-medium text-accent hover:underline">
          ← Back to bookings
        </Link>
        <h1 className="mt-1 text-lg font-semibold text-charcoal">{booking.guest_name} — room booking</h1>
        <p className="text-xs text-charcoal/40">Received {new Date(booking.created_at).toLocaleString()}</p>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        <StatusBadge value={booking.status} />
        {booking.confirmation_sms_status && (
          <span className="text-xs text-charcoal/50">
            SMS: <StatusBadge value={booking.confirmation_sms_status} />
          </span>
        )}
      </div>

      <div className="mb-6 rounded-lg border border-sand bg-white p-4">
        <p className="mb-3 text-xs text-charcoal/40">
          {booking.status === "pending_review"
            ? "Double check every field against what the guest actually said before confirming — this is what goes out by SMS."
            : "This booking has already been reviewed."}
        </p>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-xs text-charcoal/40">Check-in date</p>
            <p className="text-charcoal">{booking.check_in_date}</p>
          </div>
          <div>
            <p className="text-xs text-charcoal/40">Check-out date</p>
            <p className="text-charcoal">{booking.check_out_date}</p>
          </div>
          <div>
            <p className="text-xs text-charcoal/40">Guests</p>
            <p className="text-charcoal">{booking.num_guests}</p>
          </div>
          <div>
            <p className="text-xs text-charcoal/40">Room type</p>
            <p className="text-charcoal">{booking.room_type_name ?? "Unknown"}</p>
          </div>
          <div>
            <p className="text-xs text-charcoal/40">Breakfast included</p>
            <p className="text-charcoal">{booking.breakfast_included ? "Yes" : "No"}</p>
          </div>
          <div>
            <p className="text-xs text-charcoal/40">Guest phone</p>
            <p className="text-charcoal">{booking.guest_phone}</p>
          </div>
          <div className="col-span-2">
            <p className="text-xs text-charcoal/40">Special preferences</p>
            <p className="text-charcoal">{booking.special_preferences || "None"}</p>
          </div>
        </div>
        {booking.conversation_id && (
          <Link
            href={`/conversations/${booking.conversation_id}`}
            className="mt-3 inline-block text-xs font-medium text-accent hover:underline"
          >
            View source conversation →
          </Link>
        )}
      </div>

      <div className="rounded-lg border border-sand bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-charcoal">Staff review</h2>
        <RoomBookingReviewPanel
          bookingId={booking.id}
          status={booking.status}
          guestName={booking.guest_name}
          guestPhone={booking.guest_phone}
          checkInDate={booking.check_in_date}
          checkOutDate={booking.check_out_date}
          numGuests={booking.num_guests}
          breakfastIncluded={booking.breakfast_included}
          specialPreferences={booking.special_preferences}
          staffNotes={booking.staff_notes}
        />
      </div>
    </div>
  );
}
