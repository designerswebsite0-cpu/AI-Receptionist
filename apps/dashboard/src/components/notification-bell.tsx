"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";

const POLL_INTERVAL_MS = 8000;

export function NotificationBell() {
  const [count, setCount] = useState(0);
  const inFlight = useRef(false);

  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const response = await fetch("/api/notifications/unread-count", { cache: "no-store" });
      const payload = await response.json();
      if (response.ok && payload.success) setCount(payload.data.count);
    } catch {
      // Transient poll failure — the next tick tries again.
    } finally {
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  return (
    <Link href="/notifications" className="relative flex h-9 w-9 items-center justify-center rounded-md hover:bg-sand/50">
      <Bell size={18} className="text-charcoal/70" />
      {count > 0 && (
        <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-ivory">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </Link>
  );
}
