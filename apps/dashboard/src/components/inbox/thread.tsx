"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Send, Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";
import type { MessageOut } from "./types";

const POLL_INTERVAL_MS = 5000;

const BUBBLE_STYLE: Record<MessageOut["sender_type"], string> = {
  customer: "bg-sand/50 text-charcoal self-start",
  ai: "bg-primary/10 text-primary self-start",
  human: "bg-primary text-ivory self-end",
  system: "bg-accent/10 text-accent self-center italic text-xs",
};

export function ConversationThread({
  conversationId,
  initialMessages,
  aiActive,
  humanActive,
}: {
  conversationId: string;
  initialMessages: MessageOut[];
  aiActive: boolean;
  humanActive: boolean;
}) {
  const [messages, setMessages] = useState(initialMessages);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inFlight = useRef(false);

  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const response = await fetch(`/api/conversations/${conversationId}/messages?page_size=200`, {
        cache: "no-store",
      });
      const payload = await response.json();
      if (response.ok && payload.success) {
        setMessages(payload.data.items as MessageOut[]);
      }
    } catch {
      // Transient poll failure — try again next tick.
    } finally {
      inFlight.current = false;
    }
  }, [conversationId]);

  // Mark the thread read as soon as staff opens it, then keep polling for
  // new inbound messages while the thread stays open.
  useEffect(() => {
    fetch(`/api/conversations/${conversationId}/read`, { method: "POST" }).catch(() => undefined);
  }, [conversationId]);

  useEffect(() => {
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    setSendError(null);

    const response = await fetch(`/api/conversations/${conversationId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sender_type: "human", content_text: text }),
    });
    const payload = await response.json();
    setSending(false);

    if (!response.ok || !payload.success) {
      setSendError(payload?.error?.message ?? "Could not send that message. Please retry.");
      return;
    }
    setDraft("");
    setMessages((prev) => [...prev, payload.data as MessageOut]);
  }

  return (
    <div className="flex h-full flex-col">
      {humanActive === false && aiActive === false && (
        <div className="bg-accent/10 px-4 py-2 text-xs text-accent">
          This conversation isn&apos;t currently handled by AI or staff — it may need attention.
        </div>
      )}

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && <p className="text-center text-sm text-charcoal/40">No messages yet.</p>}
        {messages.map((message) => (
          <div key={message.id} className="flex flex-col">
            <div
              className={cn(
                "max-w-[75%] rounded-lg px-3 py-2 text-sm leading-relaxed",
                BUBBLE_STYLE[message.sender_type],
              )}
            >
              {message.sender_type === "human" && (
                <p className="mb-0.5 text-[10px] uppercase tracking-widest text-ivory/70">Staff</p>
              )}
              <p className="whitespace-pre-wrap break-words">{message.content_text ?? "(no text content)"}</p>
            </div>
            <span
              className={cn(
                "mt-0.5 text-[10px] text-charcoal/35",
                message.sender_type === "human" ? "self-end" : "self-start",
              )}
            >
              {message.sender_type} · {new Date(message.created_at).toLocaleString()}
              {message.delivery_status === "failed" && <span className="ml-1 text-red-500">failed</span>}
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSend} className="border-t border-sand/70 bg-white p-3">
        {humanActive === false && (
          <p className="mb-2 text-xs text-charcoal/50">
            AI is currently handling this conversation — sending a reply here takes over from AI.
          </p>
        )}
        <div className="flex gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                e.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="Type a reply to the guest…"
            rows={1}
            className="max-h-32 flex-1 resize-none rounded-md border border-sand px-3 py-2 text-sm focus:outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={sending || !draft.trim()}
            aria-label="Send message"
            className="flex shrink-0 items-center justify-center rounded-md bg-primary px-4 text-ivory hover:bg-primary-dark disabled:opacity-40"
          >
            {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </div>
        {sendError && <p className="mt-1 text-xs text-red-600">{sendError}</p>}
      </form>
    </div>
  );
}
