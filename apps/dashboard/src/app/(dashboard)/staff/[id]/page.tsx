import Link from "next/link";
import { StaffEditPanel } from "@/components/staff/staff-edit-panel";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi } from "@/lib/server-api";

type StaffUser = {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  role: string;
  status: string;
  last_login_at: string | null;
  created_at: string;
  assigned_conversation_count: number;
};

export default async function StaffProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const response = await fetchFromApi(`/api/v1/users/${id}`);

  if (response.status === 404) {
    return (
      <div className="mx-auto max-w-2xl">
        <p className="text-sm text-red-600">Staff member not found.</p>
      </div>
    );
  }

  const staff: StaffUser = (await response.json()).data;

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <Link href="/staff" className="text-xs font-medium text-accent hover:underline">
          ← Back to staff
        </Link>
        <h1 className="mt-1 text-lg font-semibold text-charcoal">{staff.full_name || staff.email}</h1>
        <p className="text-sm text-charcoal/50">{staff.email}</p>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        <StatusBadge value={staff.status} />
      </div>

      <div className="mb-6 grid grid-cols-2 gap-4 rounded-lg border border-sand bg-white p-4 text-sm">
        <div>
          <p className="text-xs text-charcoal/40">Role</p>
          <p className="text-charcoal">{staff.role}</p>
        </div>
        <div>
          <p className="text-xs text-charcoal/40">Open conversations assigned</p>
          <p className="text-charcoal">{staff.assigned_conversation_count}</p>
        </div>
        <div>
          <p className="text-xs text-charcoal/40">Last login</p>
          <p className="text-charcoal">{staff.last_login_at ? new Date(staff.last_login_at).toLocaleString() : "Never"}</p>
        </div>
        <div>
          <p className="text-xs text-charcoal/40">Account created</p>
          <p className="text-charcoal">{new Date(staff.created_at).toLocaleDateString()}</p>
        </div>
      </div>

      <div className="rounded-lg border border-sand bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-charcoal">Edit profile</h2>
        <StaffEditPanel
          userId={staff.id}
          initialFullName={staff.full_name}
          initialRole={staff.role}
          initialStatus={staff.status}
        />
      </div>
    </div>
  );
}
