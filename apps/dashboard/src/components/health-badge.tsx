"use client";

import { useEffect, useState } from "react";

type Status = "checking" | "ok" | "down";

export function HealthBadge() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    fetch(`${apiBaseUrl}/healthz`)
      .then((res) => setStatus(res.ok ? "ok" : "down"))
      .catch(() => setStatus("down"));
  }, []);

  const color =
    status === "ok" ? "bg-green-500" : status === "down" ? "bg-red-500" : "bg-gray-300";
  const label = status === "ok" ? "API online" : status === "down" ? "API unreachable" : "Checking…";

  return (
    <span className="inline-flex items-center gap-2 text-xs text-gray-500">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      {label}
    </span>
  );
}
