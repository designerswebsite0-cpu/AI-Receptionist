import { HealthBadge } from "@/components/health-badge";
import { UserProfileButton, type DashboardUser } from "@/components/user-profile-button";

export function Header({ user }: { user: DashboardUser }) {
  return (
    <header className="flex items-center justify-between border-b border-sand/70 bg-white px-4 py-2.5 sm:px-6">
      <UserProfileButton user={user} />
      <div className="flex items-center gap-3">
        <HealthBadge />
      </div>
    </header>
  );
}
