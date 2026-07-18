const COLOR_MAP: Record<string, string> = {
  // status / approval_status / processing_status
  active: "bg-green-100 text-green-800",
  approved: "bg-green-100 text-green-800",
  completed: "bg-green-100 text-green-800",
  clean: "bg-green-100 text-green-800",
  draft: "bg-gray-100 text-gray-700",
  pending: "bg-yellow-100 text-yellow-800",
  needs_review: "bg-yellow-100 text-yellow-800",
  extracting: "bg-yellow-100 text-yellow-800",
  embedding: "bg-yellow-100 text-yellow-800",
  chunking: "bg-yellow-100 text-yellow-800",
  rejected: "bg-red-100 text-red-800",
  failed: "bg-red-100 text-red-800",
  infected: "bg-red-100 text-red-800",
  archived: "bg-gray-200 text-gray-600",
  superseded: "bg-gray-200 text-gray-600",
  // visibility
  guest: "bg-blue-100 text-blue-800",
  staff: "bg-purple-100 text-purple-800",
  internal: "bg-purple-100 text-purple-800",
  template: "bg-gray-100 text-gray-700",
  // priority
  critical: "bg-red-100 text-red-800",
  high: "bg-orange-100 text-orange-800",
  normal: "bg-gray-100 text-gray-700",
  low: "bg-gray-100 text-gray-500",
};

export function StatusBadge({ value }: { value: string | null | undefined }) {
  if (!value) return null;
  const classes = COLOR_MAP[value] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${classes}`}>
      {value.replace(/_/g, " ")}
    </span>
  );
}
