import { type LucideIcon } from "lucide-react";

interface Props {
  icon: LucideIcon;
  title: string;
  note: string;
}

/** An honest, transparent "not built yet" notice for a sidebar section
 * whose page hasn't landed in this Phase X rollout yet — not a fake
 * feature screen, just a clear status. Replaced with the real page as
 * each stage completes within this same rollout. */
export function ComingSoon({ icon: Icon, title, note }: Props) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-sand text-center">
      <Icon size={32} className="text-charcoal/30" aria-hidden="true" />
      <h1 className="text-lg font-semibold text-charcoal">{title}</h1>
      <p className="max-w-md text-sm text-charcoal/50">{note}</p>
    </div>
  );
}
