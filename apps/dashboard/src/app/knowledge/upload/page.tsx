import { redirect } from "next/navigation";
import { DashboardNav } from "@/components/dashboard-nav";
import { SourceUploadForm } from "@/components/source-upload-form";
import { getServerAccessToken } from "@/lib/server-api";

export default async function UploadSourcePage() {
  const token = await getServerAccessToken();
  if (!token) redirect("/login");

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <DashboardNav />
      <h1 className="mb-6 text-lg font-semibold">Upload a Knowledge Source</h1>
      <SourceUploadForm />
    </main>
  );
}
