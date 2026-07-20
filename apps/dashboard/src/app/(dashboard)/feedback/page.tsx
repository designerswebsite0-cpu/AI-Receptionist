import { ThumbsDown, ThumbsUp } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { FeedbackStatusSelect } from "@/components/feedback/feedback-status-select";
import { fetchFromApi } from "@/lib/server-api";

type FeedbackItem = {
  id: string;
  category: string;
  rating: string;
  comment: string | null;
  customer_name: string | null;
  status: string;
  created_at: string;
};

type FeedbackStats = {
  total: number;
  up_count: number;
  down_count: number;
  positive_rate: number | null;
  by_category: Record<string, number>;
};

export default async function FeedbackPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const rating = params.rating ?? "";
  const status = params.status ?? "";

  const query = new URLSearchParams();
  if (rating) query.set("rating", rating);
  if (status) query.set("status", status);
  query.set("page_size", "50");

  const [statsResponse, listResponse] = await Promise.all([
    fetchFromApi("/api/v1/feedback/stats"),
    fetchFromApi(`/api/v1/feedback?${query.toString()}`),
  ]);

  const stats: FeedbackStats | null = statsResponse.ok ? (await statsResponse.json()).data : null;
  const listPayload = await listResponse.json();
  const items: FeedbackItem[] = listResponse.ok ? listPayload.data.items : [];

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-charcoal">Customer Feedback</h1>
        <p className="text-sm text-charcoal/50">Real guest thumbs-up/down from the website chat — no fabricated scores.</p>
      </div>

      {stats && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-sand bg-white p-4">
            <p className="text-xs text-charcoal/40">Total feedback</p>
            <p className="text-xl font-semibold text-charcoal">{stats.total}</p>
          </div>
          <div className="rounded-lg border border-sand bg-white p-4">
            <p className="flex items-center gap-1 text-xs text-charcoal/40">
              <ThumbsUp size={12} /> Positive
            </p>
            <p className="text-xl font-semibold text-green-700">{stats.up_count}</p>
          </div>
          <div className="rounded-lg border border-sand bg-white p-4">
            <p className="flex items-center gap-1 text-xs text-charcoal/40">
              <ThumbsDown size={12} /> Negative
            </p>
            <p className="text-xl font-semibold text-red-700">{stats.down_count}</p>
          </div>
          <div className="rounded-lg border border-sand bg-white p-4">
            <p className="text-xs text-charcoal/40">Positive rate</p>
            <p className="text-xl font-semibold text-charcoal">
              {stats.positive_rate != null ? `${Math.round(stats.positive_rate * 100)}%` : "—"}
            </p>
          </div>
        </div>
      )}

      <form className="mb-4 flex gap-3 text-sm" method="GET">
        <select name="rating" defaultValue={rating} className="rounded-md border border-sand px-3 py-1.5">
          <option value="">All ratings</option>
          <option value="up">Positive</option>
          <option value="down">Negative</option>
        </select>
        <select name="status" defaultValue={status} className="rounded-md border border-sand px-3 py-1.5">
          <option value="">All statuses</option>
          <option value="new">New</option>
          <option value="reviewed">Reviewed</option>
          <option value="actioned">Actioned</option>
          <option value="dismissed">Dismissed</option>
        </select>
        <button type="submit" className="rounded-md border border-sand px-3 py-1.5 hover:bg-sand/40">
          Filter
        </button>
      </form>

      {items.length === 0 ? (
        <EmptyState icon={ThumbsUp} title="No feedback yet" description="Nothing matches this filter yet." />
      ) : (
        <div className="space-y-2">
          {items.map((f) => (
            <div key={f.id} className="flex items-start justify-between gap-3 rounded-lg border border-sand bg-white p-3 text-sm">
              <div className="flex items-start gap-2">
                {f.rating === "up" ? (
                  <ThumbsUp size={16} className="mt-0.5 text-green-600" />
                ) : (
                  <ThumbsDown size={16} className="mt-0.5 text-red-600" />
                )}
                <div>
                  <p className="text-charcoal">{f.comment || <span className="text-charcoal/40">No comment left</span>}</p>
                  <p className="mt-1 text-xs text-charcoal/40">
                    {f.customer_name || "Guest"} · {f.category.replace(/_/g, " ")} ·{" "}
                    {new Date(f.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
              <FeedbackStatusSelect feedbackId={f.id} initialStatus={f.status} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
