import { redirect } from "next/navigation";
import { DashboardNav } from "@/components/dashboard-nav";
import { SearchPlayground } from "@/components/search-playground";
import { getServerAccessToken } from "@/lib/server-api";

export default async function SearchPlaygroundPage() {
  const token = await getServerAccessToken();
  if (!token) redirect("/login");

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <DashboardNav />
      <h1 className="mb-2 text-lg font-semibold">Search Playground</h1>
      <p className="mb-6 text-sm text-gray-500">
        Test what the AI receptionist would retrieve for a guest question, with full citations and scores.
      </p>
      <SearchPlayground />
    </main>
  );
}
