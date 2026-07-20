import Link from "next/link";
import { CalendarCheck } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi } from "@/lib/server-api";

type BookingRequest = {
  id: string;
  customer_name: string | null;
  status: string;
  booking_status: string | null;
  check_in_date: string | null;
  num_nights: number | null;
  adults: number | null;
  room_category: string | null;
  created_at: string;
};

export default async function BookingsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const status = params.status ?? "";
  const bookingStatus = params.booking_status ?? "";

  const query = new URLSearchParams();
  if (status) query.set("status", status);
  if (bookingStatus) query.set("booking_status", bookingStatus);
  query.set("page_size", "50");

  const response = await fetchFromApi(`/api/v1/bookings?${query.toString()}`);
  const payload = await response.json();
  const bookings: BookingRequest[] = response.ok ? payload.data.items : [];
  const total = response.ok ? payload.data.meta.total : 0;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-charcoal">Booking Management</h1>
        <p className="text-sm text-charcoal/50">
          {total} room booking enquiries from guests — staff follow-up required, never an auto-confirmed reservation.
        </p>
      </div>

      <form className="mb-4 flex gap-3 text-sm" method="GET">
        <select name="status" defaultValue={status} className="rounded-md border border-sand px-3 py-1.5">
          <option value="">All queue statuses</option>
          <option value="open">Open</option>
          <option value="in_progress">In progress</option>
          <option value="resolved">Resolved</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <select name="booking_status" defaultValue={bookingStatus} className="rounded-md border border-sand px-3 py-1.5">
          <option value="">All booking statuses</option>
          <option value="pending_review">Pending review</option>
          <option value="confirmed">Confirmed</option>
          <option value="rejected">Rejected</option>
          <option value="completed">Completed</option>
        </select>
        <button type="submit" className="rounded-md border border-sand px-3 py-1.5 hover:bg-sand/40">
          Filter
        </button>
      </form>

      {bookings.length === 0 ? (
        <EmptyState icon={CalendarCheck} title="No booking enquiries" description="Nothing matches this filter yet." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-sand bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-sand bg-sand/20 text-left text-xs uppercase text-charcoal/50">
              <tr>
                <th className="px-4 py-2">Guest</th>
                <th className="px-4 py-2">Check-in</th>
                <th className="px-4 py-2">Nights</th>
                <th className="px-4 py-2">Room</th>
                <th className="px-4 py-2">Queue</th>
                <th className="px-4 py-2">Booking status</th>
                <th className="px-4 py-2">Received</th>
              </tr>
            </thead>
            <tbody>
              {bookings.map((b) => (
                <tr key={b.id} className="border-b border-sand/50 last:border-0 hover:bg-sand/10">
                  <td className="px-4 py-2">
                    <Link href={`/bookings/${b.id}`} className="font-medium text-charcoal hover:underline">
                      {b.customer_name || `Guest ${b.id.slice(0, 8)}`}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-charcoal/60">{b.check_in_date ?? "—"}</td>
                  <td className="px-4 py-2 text-charcoal/60">{b.num_nights ?? "—"}</td>
                  <td className="px-4 py-2 text-charcoal/60">{b.room_category ?? "—"}</td>
                  <td className="px-4 py-2">
                    <StatusBadge value={b.status} />
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge value={b.booking_status ?? "pending_review"} />
                  </td>
                  <td className="px-4 py-2 text-xs text-charcoal/40">{new Date(b.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
