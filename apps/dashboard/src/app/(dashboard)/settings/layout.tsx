"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";

const TABS = [
  { href: "/settings/general", label: "General" },
  { href: "/settings/integrations", label: "Integrations" },
  { href: "/settings/audit-logs", label: "Audit Logs" },
  { href: "/settings/system", label: "System Monitoring" },
];

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-4 text-lg font-semibold text-charcoal">Settings</h1>
      <div className="mb-6 flex gap-1 border-b border-sand">
        {TABS.map((tab) => (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              "border-b-2 px-3 py-2 text-sm font-medium",
              pathname === tab.href
                ? "border-accent text-charcoal"
                : "border-transparent text-charcoal/50 hover:text-charcoal",
            )}
          >
            {tab.label}
          </Link>
        ))}
      </div>
      {children}
    </div>
  );
}
