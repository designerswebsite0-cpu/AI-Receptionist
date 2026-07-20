import {
  LayoutDashboard,
  Inbox,
  Users,
  BookOpen,
  UserCog,
  CalendarCheck,
  Bell,
  MessageSquareHeart,
  Settings,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

/** The 9 required sidebar sections (Phase X). Items are only added here
 * once their real page exists — never a dead link to an unbuilt section. */
export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard & Analytics", icon: LayoutDashboard },
  { href: "/conversations", label: "Inbox", icon: Inbox },
  { href: "/customers", label: "Customer 360", icon: Users },
  { href: "/knowledge", label: "Knowledge Base", icon: BookOpen },
  { href: "/staff", label: "Staff Management", icon: UserCog },
  { href: "/bookings", label: "Booking Management", icon: CalendarCheck },
  { href: "/notifications", label: "Notifications", icon: Bell },
  { href: "/feedback", label: "Customer Feedback", icon: MessageSquareHeart },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function isActiveNavHref(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
