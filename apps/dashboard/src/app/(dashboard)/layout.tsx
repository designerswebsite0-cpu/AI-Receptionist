import { redirect } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { Header } from "@/components/header";
import { ResortSetupForm } from "@/components/resort-setup-form";
import { fetchFromApi } from "@/lib/server-api";
import type { DashboardUser } from "@/components/user-profile-button";

type MeResponse = {
  user_id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  role: string | null;
  status: string | null;
  last_login_at: string | null;
  resort_configured: boolean;
};

/** The one place every dashboard route's auth check now lives — replaces
 * the `getServerAccessToken()` + redirect duplicated across every page. */
export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  // 20s revalidation — see fetchFromApi's docstring. This is the one call
  // that ran fresh on literally every navigation before the page's own
  // data even started fetching; "who's logged in" doesn't need to be
  // millisecond-fresh, so this alone removes a full sequential round-trip
  // to the backend from most section-to-section navigation.
  const meResponse = await fetchFromApi("/api/v1/auth/me", {}, { revalidateSeconds: 20 });
  if (meResponse.status === 401) {
    redirect("/login?reason=expired");
  }
  if (!meResponse.ok) {
    redirect("/login");
  }

  const me = (await meResponse.json()).data as MeResponse;

  if (!me.resort_configured) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-sand/20 px-4 py-10">
        <div className="w-full max-w-lg">
          <h1 className="mb-1 text-lg font-semibold text-charcoal">Welcome — let&apos;s set up your resort</h1>
          <p className="mb-6 text-sm text-charcoal/60">
            This one-time setup configures the resort profile the AI receptionist and dashboard use everywhere else.
          </p>
          <ResortSetupForm />
        </div>
      </main>
    );
  }

  const user: DashboardUser = {
    email: me.email,
    full_name: me.full_name,
    avatar_url: me.avatar_url,
    role: me.role,
    status: me.status,
    last_login_at: me.last_login_at,
  };

  return (
    <div className="flex min-h-screen flex-col bg-sand/20 lg:flex-row">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header user={user} />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
