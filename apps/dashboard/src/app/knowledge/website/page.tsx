import { redirect } from "next/navigation";
import { DashboardNav } from "@/components/dashboard-nav";
import { WebsiteCrawlForm } from "@/components/website-crawl-form";
import { getServerAccessToken } from "@/lib/server-api";

export default async function WebsiteCrawlPage() {
  const token = await getServerAccessToken();
  if (!token) redirect("/login");

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <DashboardNav />
      <h1 className="mb-2 text-lg font-semibold">Website Crawl</h1>
      <p className="mb-6 text-sm text-gray-500">
        Crawl the resort&apos;s live website and index its guest-facing pages. Approved source PDFs and governance
        corrections always take precedence over website text.
      </p>
      <WebsiteCrawlForm />
    </main>
  );
}
