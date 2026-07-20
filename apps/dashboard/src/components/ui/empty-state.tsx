import { ReactNode } from "react";
import { type LucideIcon } from "lucide-react";

interface Props {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}

/** Used whenever a list genuinely has zero rows — never fabricated
 * placeholder data, just an honest "nothing here yet" state with a way
 * forward when one exists (e.g. an upload/create action). */
export function EmptyState({ icon: Icon, title, description, action }: Props) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-sand py-16 text-center">
      {Icon && <Icon size={28} className="text-charcoal/30" aria-hidden="true" />}
      <p className="text-sm font-medium text-charcoal">{title}</p>
      {description && <p className="max-w-sm text-xs text-charcoal/50">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
