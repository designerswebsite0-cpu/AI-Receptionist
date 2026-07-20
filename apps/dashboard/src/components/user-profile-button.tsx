"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, LogOut, Mail, Shield } from "lucide-react";
import { useRouter } from "next/navigation";

export interface DashboardUser {
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  role: string | null;
  status: string | null;
  last_login_at: string | null;
}

function initials(name: string | null, email: string): string {
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/);
    return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase();
  }
  return email[0]?.toUpperCase() ?? "?";
}

/** Top-left profile button (per Phase X brief: "close to the sidebar/header
 * region"). No role/permission enforcement — role is purely informational,
 * defaulting to "Administrator" until Staff Management (Stage 4) adds a
 * real column, per the brief's explicit "keep architecture ready for future
 * roles without implementing enforcement" instruction. */
export function UserProfileButton({ user }: { user: DashboardUser }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  const displayName = user.full_name || user.email;
  const role = user.role || "Administrator";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="true"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-md px-2 py-1.5 text-left hover:bg-sand/50"
      >
        {user.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={user.avatar_url} alt="" className="h-8 w-8 rounded-full object-cover" />
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-xs font-semibold text-ivory">
            {initials(user.full_name, user.email)}
          </div>
        )}
        <div className="hidden sm:block">
          <p className="text-sm font-medium leading-tight text-charcoal">{displayName}</p>
          <p className="text-[11px] leading-tight text-charcoal/50">{role}</p>
        </div>
        <ChevronDown size={14} className="text-charcoal/40" aria-hidden="true" />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-40 mt-1 w-64 rounded-md border border-sand bg-white py-2 shadow-lg">
          <div className="border-b border-sand/70 px-4 pb-3">
            <p className="text-sm font-semibold text-charcoal">{displayName}</p>
            <p className="mt-0.5 flex items-center gap-1 text-xs text-charcoal/60">
              <Mail size={12} /> {user.email}
            </p>
            <p className="mt-0.5 flex items-center gap-1 text-xs text-charcoal/60">
              <Shield size={12} /> {role}
              {user.status && <span className="text-charcoal/40">· {user.status}</span>}
            </p>
            {user.last_login_at && (
              <p className="mt-1 text-[11px] text-charcoal/40">
                Last login {new Date(user.last_login_at).toLocaleString()}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50"
          >
            <LogOut size={14} /> Log out
          </button>
        </div>
      )}
    </div>
  );
}
