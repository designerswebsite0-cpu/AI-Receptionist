"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";

type NotificationOut = {
  id: string;
  notification_type: string;
  title: string;
  body: string | null;
  resource_type: string | null;
  resource_id: string | null;
  read_at: string | null;
  created_at: string;
};

const POLL_INTERVAL_MS = 15000;

const RESOURCE_HREF: Record<string, (id: string) => string> = {
  conversation: (id) => `/conversations/${id}`,
  service_request: (id) => `/bookings/${id}`,
  knowledge_source: (id) => `/knowledge/${id}`,
};

function resourceHref(resourceType: string | null, resourceId: string | null): string | null {
  if (!resourceType || !resourceId) return null;
  return RESOURCE_HREF[resourceType]?.(resourceId) ?? null;
}

export function NotificationList({ initialNotifications }: { initialNotifications: NotificationOut[] }) {
  const [notifications, setNotifications] = useState(initialNotifications);
  const [markingAll, setMarkingAll] = useState(false);
  const inFlight = useRef(false);

  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const response = await fetch("/api/notifications?page_size=50", { cache: "no-store" });
      const payload = await response.json();
      if (response.ok && payload.success) setNotifications(payload.data.items);
    } catch {
      // Transient poll failure — the next tick tries again.
    } finally {
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  async function markRead(id: string) {
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n)));
    await fetch(`/api/notifications/${id}/read`, { method: "POST" });
  }

  async function markAllRead() {
    setMarkingAll(true);
    await fetch("/api/notifications/read-all", { method: "POST" });
    setMarkingAll(false);
    refresh();
  }

  const unreadCount = notifications.filter((n) => !n.read_at).length;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-charcoal/50">{unreadCount} unread</p>
        <Button variant="secondary" size="sm" onClick={markAllRead} loading={markingAll} disabled={unreadCount === 0}>
          Mark all read
        </Button>
      </div>

      {notifications.length === 0 ? (
        <EmptyState icon={Bell} title="No notifications" description="You're all caught up." />
      ) : (
        <div className="space-y-2">
          {notifications.map((n) => {
            const href = resourceHref(n.resource_type, n.resource_id);
            const isUnread = !n.read_at;
            const content = (
              <div
                className={`flex items-start justify-between gap-3 rounded-lg border p-3 text-sm ${
                  isUnread ? "border-accent/30 bg-accent/5" : "border-sand bg-white"
                }`}
              >
                <div>
                  <p className={`font-medium ${isUnread ? "text-charcoal" : "text-charcoal/70"}`}>{n.title}</p>
                  {n.body && <p className="mt-0.5 text-xs text-charcoal/50">{n.body}</p>}
                  <p className="mt-1 text-[11px] text-charcoal/40">{new Date(n.created_at).toLocaleString()}</p>
                </div>
                {isUnread && <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-accent" />}
              </div>
            );

            return href ? (
              <Link key={n.id} href={href} onClick={() => isUnread && markRead(n.id)} className="block">
                {content}
              </Link>
            ) : (
              <button
                key={n.id}
                type="button"
                onClick={() => isUnread && markRead(n.id)}
                className="block w-full text-left"
              >
                {content}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
