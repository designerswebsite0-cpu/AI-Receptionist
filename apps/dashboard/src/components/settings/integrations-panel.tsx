"use client";

import { useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

type IntegrationsStatus = {
  supabase: { configured: boolean; reachable: boolean; project_host: string | null };
  openai: { configured: boolean; masked_key: string | null; chat_model: string; embedding_model: string };
  groq: { configured: boolean; masked_key: string | null; model: string; role: string };
  redis: { configured: boolean; note: string | null };
};

function StatusDot({ ok }: { ok: boolean }) {
  return ok ? (
    <CheckCircle2 size={16} className="text-green-600" />
  ) : (
    <XCircle size={16} className="text-charcoal/30" />
  );
}

export function IntegrationsPanel({ initialStatus }: { initialStatus: IntegrationsStatus }) {
  const [status, setStatus] = useState(initialStatus);
  const [testing, setTesting] = useState(false);

  async function testConnection() {
    setTesting(true);
    const response = await fetch("/api/health/integrations", { cache: "no-store" });
    const payload = await response.json();
    setTesting(false);
    if (response.ok && payload.success) setStatus(payload.data);
  }

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <Button variant="secondary" size="sm" onClick={testConnection} loading={testing}>
          Test connections
        </Button>
      </div>

      <div className="space-y-3">
        <div className="rounded-lg border border-sand bg-white p-4">
          <div className="mb-1 flex items-center justify-between">
            <p className="text-sm font-semibold text-charcoal">Supabase (database + auth + storage)</p>
            <StatusDot ok={status.supabase.reachable} />
          </div>
          <p className="text-xs text-charcoal/50">Project: {status.supabase.project_host ?? "—"}</p>
        </div>

        <div className="rounded-lg border border-sand bg-white p-4">
          <div className="mb-1 flex items-center justify-between">
            <p className="text-sm font-semibold text-charcoal">OpenAI (primary LLM + embeddings)</p>
            <StatusDot ok={status.openai.configured} />
          </div>
          <p className="text-xs text-charcoal/50">
            {status.openai.configured ? `Key ${status.openai.masked_key} · ${status.openai.chat_model}` : "Not configured"}
          </p>
        </div>

        <div className="rounded-lg border border-sand bg-white p-4">
          <div className="mb-1 flex items-center justify-between">
            <p className="text-sm font-semibold text-charcoal">Groq (fallback LLM)</p>
            <StatusDot ok={status.groq.configured} />
          </div>
          <p className="text-xs text-charcoal/50">
            {status.groq.configured ? `Key ${status.groq.masked_key} · ${status.groq.model}` : "Not configured"}
          </p>
        </div>

        <div className="rounded-lg border border-sand bg-white p-4">
          <div className="mb-1 flex items-center justify-between">
            <p className="text-sm font-semibold text-charcoal">Redis</p>
            <StatusDot ok={status.redis.configured} />
          </div>
          <p className="text-xs text-charcoal/50">{status.redis.note ?? "Configured"}</p>
        </div>
      </div>
    </div>
  );
}
