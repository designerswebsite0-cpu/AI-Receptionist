import { InputHTMLAttributes, LabelHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/cn";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...rest }, ref) => (
    <input
      ref={ref}
      className={cn(
        "w-full rounded-md border border-sand bg-white px-3 py-2 text-sm text-charcoal placeholder:text-charcoal/40",
        "focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent",
        "disabled:cursor-not-allowed disabled:bg-sand/30",
        className,
      )}
      {...rest}
    />
  ),
);
Input.displayName = "Input";

export function Label({ className, ...rest }: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("mb-1 block text-sm font-medium text-charcoal", className)} {...rest} />;
}

export function FieldError({ children }: { children?: string | null }) {
  if (!children) return null;
  return <p className="mt-1 text-xs text-red-600">{children}</p>;
}
