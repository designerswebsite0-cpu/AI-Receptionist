import { NotificationList } from "@/components/notifications/notification-list";
import { fetchFromApi } from "@/lib/server-api";

export default async function NotificationsPage() {
  const response = await fetchFromApi("/api/v1/notifications?page_size=50");
  const payload = await response.json();
  const notifications = response.ok ? payload.data.items : [];

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-charcoal">Notifications</h1>
        <p className="text-sm text-charcoal/50">Real-time alerts for handoffs, bookings, and knowledge issues.</p>
      </div>
      <NotificationList initialNotifications={notifications} />
    </div>
  );
}
