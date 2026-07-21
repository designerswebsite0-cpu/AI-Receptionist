"use client";

import { useCallback, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type DashboardAnalytics = {
  summary: {
    range_start: string;
    range_end: string;
    total_conversations: number;
    open_conversations: number;
    escalated_conversations: number;
    new_customers: number;
    booking_enquiries: number;
    feedback_total: number;
    feedback_positive_rate: number | null;
    unread_notifications: number;
    avg_messages_per_conversation: number | null;
    handoff_rate: number | null;
  };
  conversations_by_day: { day: string; count: number }[];
  bookings_by_status: { label: string; count: number }[];
  feedback_by_rating: { label: string; count: number }[];
  conversations_by_status: { label: string; count: number }[];
  conversations_by_channel: { label: string; count: number }[];
  staff_workload: { label: string; count: number }[];
};

const RANGES: { key: string; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "7d", label: "7 days" },
  { key: "30d", label: "30 days" },
];

const PIE_COLORS: Record<string, string> = { up: "#1E3A2F", down: "#A3704C" };

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-sand bg-white p-4">
      <p className="text-xs text-charcoal/40">{label}</p>
      <p className="text-xl font-semibold text-charcoal">{value}</p>
    </div>
  );
}

export function DashboardOverview({ initialData }: { initialData: DashboardAnalytics }) {
  const [data, setData] = useState(initialData);
  const [range, setRange] = useState("7d");
  const [loading, setLoading] = useState(false);

  const loadRange = useCallback(async (key: string) => {
    setRange(key);
    setLoading(true);
    const response = await fetch(`/api/analytics/dashboard?range=${key}`, { cache: "no-store" });
    const payload = await response.json();
    setLoading(false);
    if (response.ok && payload.success) setData(payload.data);
  }, []);

  const { summary } = data;

  return (
    <div>
      <div className="mb-4 flex gap-2">
        {RANGES.map((r) => (
          <button
            key={r.key}
            onClick={() => loadRange(r.key)}
            disabled={loading}
            className={`rounded-md border px-3 py-1.5 text-sm ${
              range === r.key ? "border-accent bg-accent/10 text-charcoal" : "border-sand text-charcoal/60 hover:bg-sand/40"
            }`}
          >
            {r.label}
          </button>
        ))}
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Conversations" value={summary.total_conversations} />
        <StatTile label="Open now" value={summary.open_conversations} />
        <StatTile label="Escalated now" value={summary.escalated_conversations} />
        <StatTile label="New guests" value={summary.new_customers} />
        <StatTile label="Booking enquiries" value={summary.booking_enquiries} />
        <StatTile
          label="Feedback positive rate"
          value={summary.feedback_positive_rate != null ? `${Math.round(summary.feedback_positive_rate * 100)}%` : "—"}
        />
        <StatTile label="Feedback received" value={summary.feedback_total} />
        <StatTile label="Unread notifications" value={summary.unread_notifications} />
        <StatTile
          label="Avg messages / conversation"
          value={summary.avg_messages_per_conversation != null ? summary.avg_messages_per_conversation.toFixed(1) : "—"}
        />
        <StatTile
          label="Handoff rate"
          value={summary.handoff_rate != null ? `${Math.round(summary.handoff_rate * 100)}%` : "—"}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-sand bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-charcoal">Conversations per day</h2>
          {data.conversations_by_day.length === 0 ? (
            <p className="text-sm text-charcoal/40">No conversations in this range.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.conversations_by_day}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EAE5D9" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#1E3A2F" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="rounded-lg border border-sand bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-charcoal">Booking enquiries by status</h2>
          {data.bookings_by_status.length === 0 ? (
            <p className="text-sm text-charcoal/40">No booking enquiries in this range.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.bookings_by_status} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#EAE5D9" />
                <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
                <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} width={100} />
                <Tooltip />
                <Bar dataKey="count" fill="#A3704C" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="rounded-lg border border-sand bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-charcoal">Feedback breakdown</h2>
          {summary.feedback_total === 0 ? (
            <p className="text-sm text-charcoal/40">No feedback received in this range.</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={data.feedback_by_rating} dataKey="count" nameKey="label" innerRadius={40} outerRadius={70}>
                  {data.feedback_by_rating.map((entry) => (
                    <Cell key={entry.label} fill={PIE_COLORS[entry.label] ?? "#EAE5D9"} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="rounded-lg border border-sand bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-charcoal">Conversations by status</h2>
          {data.conversations_by_status.length === 0 ? (
            <p className="text-sm text-charcoal/40">No conversations in this range.</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={data.conversations_by_status} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#EAE5D9" />
                <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
                <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} width={110} />
                <Tooltip />
                <Bar dataKey="count" fill="#1E3A2F" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="rounded-lg border border-sand bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-charcoal">Conversations by channel</h2>
          {data.conversations_by_channel.length === 0 ? (
            <p className="text-sm text-charcoal/40">No conversations in this range.</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={data.conversations_by_channel} dataKey="count" nameKey="label" innerRadius={40} outerRadius={70}>
                  {data.conversations_by_channel.map((entry, i) => (
                    <Cell key={entry.label} fill={["#1E3A2F", "#A3704C", "#C9A77C"][i % 3]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="rounded-lg border border-sand bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-charcoal">Staff workload (open conversations)</h2>
          {data.staff_workload.length === 0 ? (
            <p className="text-sm text-charcoal/40">No conversations currently assigned to staff.</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={data.staff_workload} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#EAE5D9" />
                <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
                <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} width={110} />
                <Tooltip />
                <Bar dataKey="count" fill="#A3704C" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
