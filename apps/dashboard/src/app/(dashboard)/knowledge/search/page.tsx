import { SearchPlayground } from "@/components/search-playground";

export default function SearchPlaygroundPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-2 text-lg font-semibold text-charcoal">Search Playground</h1>
      <p className="mb-6 text-sm text-charcoal/50">
        Test what the AI receptionist would retrieve for a guest question, with full citations and scores.
      </p>
      <SearchPlayground />
    </div>
  );
}
