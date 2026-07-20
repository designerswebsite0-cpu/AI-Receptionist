import { clsx, type ClassValue } from "clsx";

/** Thin wrapper so every component merges conditional classNames the same
 * way, rather than each hand-rolling template-literal concatenation. */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}
