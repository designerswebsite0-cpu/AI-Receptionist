"use client";

import { useState } from "react";
import { Star, X } from "lucide-react";
import { cn } from "@/lib/cn";

export function TagsPanel({ customerId, initialTags }: { customerId: string; initialTags: string[] }) {
  const [tags, setTags] = useState(initialTags);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);

  async function addTag(e: React.FormEvent) {
    e.preventDefault();
    const tag = draft.trim().toLowerCase();
    if (!tag || tags.includes(tag) || pending) return;
    setPending(true);
    const response = await fetch(`/api/customers/${customerId}/tags`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tag }),
    });
    setPending(false);
    if (response.ok) {
      setTags((prev) => [...prev, tag]);
      setDraft("");
    }
  }

  async function removeTag(tag: string) {
    setPending(true);
    const response = await fetch(`/api/customers/${customerId}/tags/${encodeURIComponent(tag)}`, {
      method: "DELETE",
    });
    setPending(false);
    if (response.ok) setTags((prev) => prev.filter((t) => t !== tag));
  }

  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-1.5">
        {tags.map((tag) => (
          <span
            key={tag}
            className={cn(
              "flex items-center gap-1 rounded-full px-2 py-0.5 text-xs",
              tag === "vip" ? "bg-accent/15 text-accent" : "bg-sand/60 text-charcoal/70",
            )}
          >
            {tag === "vip" && <Star size={10} className="fill-accent" />}
            {tag}
            <button type="button" onClick={() => removeTag(tag)} disabled={pending} aria-label={`Remove tag ${tag}`}>
              <X size={10} />
            </button>
          </span>
        ))}
      </div>
      <form onSubmit={addTag} className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add a tag (e.g. vip)"
          className="flex-1 rounded-md border border-sand px-2 py-1 text-xs focus:outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={pending || !draft.trim()}
          className="rounded-md border border-sand px-2 py-1 text-xs hover:bg-sand/40 disabled:opacity-40"
        >
          Add
        </button>
      </form>
    </div>
  );
}
