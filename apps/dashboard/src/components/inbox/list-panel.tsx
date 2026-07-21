"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { StatusBadge } from "@/components/status-badge";
import { cn } from "@/lib/cn";
import type { ConversationOut } from "./types";

const POLL_INTERVAL_MS = 3000;

interface Filters {
  status: string;
  priority: string;
  handledBy: string; // "" | "ai" | "human"
  unreadOnly: boolean;
}

const DEFAULT_FILTERS: Filters = { status: "", priority: "", handledBy: "", unreadOnly: false };

function buildQuery(search: string, filters: Filters): string {
  const query = new URLSearchParams();
  query.set("page_size", "50");
  if (filters.status) query.set("status", filters.status);
  if (filters.priority) query.set("priority", filters.priority);
  if (filters.handledBy === "ai") query.set("ai_active", "true");
  if (filters.handledBy === "human") query.set("ai_active", "false");
  if (filters.unreadOnly) query.set("unread", "true");
  // The list endpoint has no free-text search of its own yet — filtered
  // client-side below instead of adding a backend param for one field.
  void search;
  return query.toString();
}

export function InboxListPanel({ initialConversations }: { initialConversations: ConversationOut[] }) {
  const pathname = usePathname();
  const router = useRouter();
  const [conversations, setConversations] = useState(initialConversations);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [showFilters, setShowFilters] = useState(false);
  const inFlight = useRef(false);

  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const response = await fetch(`/api/conversations?${buildQuery(search, filters)}`, { cache: "no-store" });
      const payload = await response.json();
      if (response.ok && payload.success) {
        setConversations(payload.data.items as ConversationOut[]);
      }
    } catch {
      // Transient poll failure — the next tick tries again.
    } finally {
      inFlight.current = false;
    }
  }, [search, filters]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  const visible = conversations.filter((c) => {
    if (!search.trim()) return true;
    const needle = search.trim().toLowerCase();
    return (
      (c.customer_name ?? "").toLowerCase().includes(needle) ||
      c.channel.toLowerCase().includes(needle) ||
      (c.summary ?? "").toLowerCase().includes(needle)
    );
  });

  return (
    <div className="flex h-full w-full flex-col border-r border-sand/70 bg-white lg:w-80 lg:shrink-0">
      <div className="border-b border-sand/70 p-3">
        <div className="relative">
          <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-charcoal/30" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations…"
            className="w-full rounded-md border border-sand py-1.5 pl-8 pr-2 text-sm focus:outline-none focus:border-accent"
          />
        </div>
        <button
          type="button"
          onClick={() => setShowFilters((v) => !v)}
          className="mt-2 text-xs font-medium text-charcoal/60 hover:text-charcoal"
        >
          {showFilters ? "Hide filters" : "Filters"}
        </button>
        {showFilters && (
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
            <select
              value={filters.status}
              onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
              className="rounded-md border border-sand px-2 py-1"
            >
              <option value="">All statuses</option>
              <option value="open">open</option>
              <option value="waiting_for_guest">waiting for guest</option>
              <option value="waiting_for_staff">waiting for staff</option>
              <option value="ai_handling">ai handling</option>
              <option value="human_handling">human handling</option>
              <option value="escalated">escalated</option>
              <option value="closed">closed</option>
            </select>
            <select
              value={filters.priority}
              onChange={(e) => setFilters((f) => ({ ...f, priority: e.target.value }))}
              className="rounded-md border border-sand px-2 py-1"
            >
              <option value="">All priorities</option>
              <option value="urgent">urgent</option>
              <option value="high">high</option>
              <option value="normal">normal</option>
              <option value="low">low</option>
            </select>
            <select
              value={filters.handledBy}
              onChange={(e) => setFilters((f) => ({ ...f, handledBy: e.target.value }))}
              className="rounded-md border border-sand px-2 py-1"
            >
              <option value="">AI or staff</option>
              <option value="ai">AI handling</option>
              <option value="human">Staff handling</option>
            </select>
            <label className="flex items-center gap-1.5 rounded-md border border-sand px-2 py-1">
              <input
                type="checkbox"
                checked={filters.unreadOnly}
                onChange={(e) => setFilters((f) => ({ ...f, unreadOnly: e.target.checked }))}
              />
              Unread only
            </label>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {visible.length === 0 && (
          <p className="p-4 text-center text-sm text-charcoal/40">No conversations match.</p>
        )}
        {visible.map((c) => {
          const href = `/conversations/${c.id}`;
          const active = pathname === href;
          return (
            <Link
              key={c.id}
              href={href}
              onClick={() => router.prefetch(href)}
              className={cn(
                "block border-b border-sand/40 px-3 py-3 hover:bg-sand/20",
                active && "bg-sand/30",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-medium text-charcoal">
                  {c.customer_name || `Guest ${c.customer_id.slice(0, 8)}`}
                </span>
                {c.unread_count > 0 && (
                  <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-ivory">
                    {c.unread_count}
                  </span>
                )}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1">
                <StatusBadge value={c.status} />
                {c.priority !== "normal" && <StatusBadge value={c.priority} />}
                <span className="text-[10px] uppercase text-charcoal/40">{c.channel}</span>
              </div>
              <p className="mt-1 truncate text-xs text-charcoal/50">
                {c.human_active ? "Staff handling" : c.ai_active ? "AI handling" : "Unhandled"}
                {c.last_message_at && ` · ${new Date(c.last_message_at).toLocaleString()}`}
              </p>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
