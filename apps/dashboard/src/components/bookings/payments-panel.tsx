"use client";

import { useEffect, useState, useCallback } from "react";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

type Payment = {
  id: string;
  amount: number;
  currency: string;
  method: string;
  status: string;
  staff_notes: string | null;
  created_at: string;
};

const METHOD_LABELS: Record<string, string> = {
  cash: "Cash",
  card_on_arrival: "Card on arrival",
  bank_transfer: "Bank transfer",
  online_pending: "Online (pending — no gateway yet)",
};

export function PaymentsPanel({ roomBookingId, customerId }: { roomBookingId: string; customerId: string }) {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ amount: "", method: "cash", staff_notes: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const response = await fetch(`/api/payments?room_booking_id=${roomBookingId}&page_size=20`);
    const payload = await response.json();
    if (payload.success) setPayments(payload.data.items);
    setLoading(false);
  }, [roomBookingId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleRecord(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    const response = await fetch("/api/payments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        room_booking_id: roomBookingId,
        customer_id: customerId,
        amount: Number(form.amount),
        method: form.method,
        staff_notes: form.staff_notes || null,
      }),
    });
    const payload = await response.json();
    setSaving(false);
    if (!response.ok || !payload.success) {
      setError(payload?.error?.message ?? "Could not record payment.");
      return;
    }
    setForm({ amount: "", method: "cash", staff_notes: "" });
    load();
  }

  async function handleRefund(paymentId: string) {
    if (!window.confirm("Mark this payment as refunded?")) return;
    await fetch(`/api/payments/${paymentId}/refund`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    load();
  }

  return (
    <div className="rounded-lg border border-sand bg-white p-4">
      <h2 className="mb-1 text-sm font-semibold text-charcoal">Payments</h2>
      <p className="mb-3 text-xs text-charcoal/40">
        No online gateway is connected yet — record money collected in person, or log a guest&apos;s intent to pay online.
      </p>

      {loading ? (
        <p className="text-xs text-charcoal/40">Loading…</p>
      ) : payments.length === 0 ? (
        <p className="mb-3 text-xs text-charcoal/40">No payments recorded yet.</p>
      ) : (
        <div className="mb-3 space-y-2">
          {payments.map((p) => (
            <div key={p.id} className="flex items-center justify-between rounded-md border border-sand/60 px-3 py-2 text-sm">
              <div>
                <span className="font-medium text-charcoal">
                  {p.currency} {p.amount.toFixed(2)}
                </span>
                <span className="ml-2 text-xs text-charcoal/50">{METHOD_LABELS[p.method] ?? p.method}</span>
                {p.staff_notes && <p className="text-xs text-charcoal/40">{p.staff_notes}</p>}
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge value={p.status} />
                {p.status === "paid" && (
                  <button
                    type="button"
                    onClick={() => handleRefund(p.id)}
                    className="text-xs font-medium text-red-600 hover:underline"
                  >
                    Refund
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={handleRecord} className="flex flex-wrap items-end gap-2 border-t border-sand pt-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-charcoal/60">Amount</label>
          <input
            type="number"
            step="0.01"
            min="0"
            required
            value={form.amount}
            onChange={(e) => setForm({ ...form, amount: e.target.value })}
            className="w-28 rounded-md border border-sand px-2 py-1.5 text-sm focus:outline-none focus:border-accent"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-charcoal/60">Method</label>
          <select
            value={form.method}
            onChange={(e) => setForm({ ...form, method: e.target.value })}
            className="rounded-md border border-sand px-2 py-1.5 text-sm focus:outline-none focus:border-accent"
          >
            <option value="cash">Cash</option>
            <option value="card_on_arrival">Card on arrival</option>
            <option value="bank_transfer">Bank transfer</option>
            <option value="online_pending">Online (pending)</option>
          </select>
        </div>
        <div className="flex-1 min-w-[120px]">
          <label className="mb-1 block text-xs font-medium text-charcoal/60">Notes</label>
          <input
            value={form.staff_notes}
            onChange={(e) => setForm({ ...form, staff_notes: e.target.value })}
            className="w-full rounded-md border border-sand px-2 py-1.5 text-sm focus:outline-none focus:border-accent"
          />
        </div>
        <Button type="submit" size="sm" loading={saving}>
          Record
        </Button>
      </form>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}
