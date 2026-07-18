import Link from "next/link";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/conversations", label: "Conversations" },
  { href: "/knowledge", label: "Knowledge Sources" },
  { href: "/knowledge/upload", label: "Upload" },
  { href: "/knowledge/search", label: "Search Playground" },
  { href: "/knowledge/jobs", label: "Ingestion Jobs" },
  { href: "/knowledge/website", label: "Website Crawl" },
];

export function DashboardNav() {
  return (
    <nav className="mb-6 flex flex-wrap gap-x-4 gap-y-2 border-b border-gray-200 pb-4 text-sm">
      {LINKS.map((link) => (
        <Link key={link.href} href={link.href} className="text-gray-600 hover:text-gray-900 hover:underline">
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
