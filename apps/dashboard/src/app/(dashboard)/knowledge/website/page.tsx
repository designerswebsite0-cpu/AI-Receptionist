import { WebsiteCrawlForm } from "@/components/website-crawl-form";

export default function WebsiteCrawlPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-2 text-lg font-semibold text-charcoal">Website Crawl</h1>
      <p className="mb-6 text-sm text-charcoal/50">
        Crawl the resort&apos;s live website and index its guest-facing pages. Approved source PDFs and governance
        corrections always take precedence over website text.
      </p>
      <WebsiteCrawlForm />
    </div>
  );
}
