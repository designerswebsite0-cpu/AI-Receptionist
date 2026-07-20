"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import { NAV_ITEMS, isActiveNavHref } from "@/lib/nav-config";
import { cn } from "@/lib/cn";

function NavLinks({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-1 flex-col gap-1 px-3 py-4">
      {NAV_ITEMS.map((item) => {
        const active = isActiveNavHref(pathname, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              active ? "bg-primary text-ivory" : "text-charcoal/70 hover:bg-sand/50 hover:text-charcoal",
            )}
          >
            <item.icon size={18} aria-hidden="true" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-sand/70 bg-white lg:flex">
        <div className="flex items-center gap-2 border-b border-sand/70 px-5 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-semibold text-ivory">
            R
          </div>
          <div>
            <p className="text-sm font-semibold leading-tight text-charcoal">RKPR Resort</p>
            <p className="text-[11px] leading-tight text-charcoal/50">Operations Dashboard</p>
          </div>
        </div>
        <NavLinks pathname={pathname} />
      </aside>

      {/* Mobile top bar + drawer */}
      <div className="flex items-center justify-between border-b border-sand/70 bg-white px-4 py-3 lg:hidden">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-ivory">
            R
          </div>
          <p className="text-sm font-semibold text-charcoal">RKPR Resort</p>
        </div>
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          aria-label="Open navigation menu"
          className="rounded-md p-2 text-charcoal/70 hover:bg-sand/50"
        >
          <Menu size={20} />
        </button>
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-charcoal/40" onClick={() => setMobileOpen(false)} aria-hidden="true" />
          <div className="absolute inset-y-0 left-0 flex w-72 flex-col bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-sand/70 px-5 py-4">
              <p className="text-sm font-semibold text-charcoal">RKPR Resort</p>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                aria-label="Close navigation menu"
                className="rounded-md p-1.5 text-charcoal/70 hover:bg-sand/50"
              >
                <X size={18} />
              </button>
            </div>
            <NavLinks pathname={pathname} onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}
    </>
  );
}
