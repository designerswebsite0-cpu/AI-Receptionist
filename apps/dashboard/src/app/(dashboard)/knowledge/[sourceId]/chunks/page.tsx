import Link from "next/link";
import { StatusBadge } from "@/components/status-badge";
import { fetchFromApi } from "@/lib/server-api";

type ChunkOut = {
  id: string;
  chunk_key: string;
  chunk_type: string;
  chunk_index: number;
  content_raw: string;
  section_title: string | null;
  heading_path: string | null;
  page_number: number | null;
  token_count: number | null;
  status: string;
  retrieval_enabled: boolean;
};

type ChunkListResponse = { items: ChunkOut[]; total: number; offset: number; limit: number };

export default async function SourceChunksPage({
  params,
  searchParams,
}: {
  params: Promise<{ sourceId: string }>;
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { sourceId } = await params;
  const sp = await searchParams;
  const page = Number(sp.page ?? "1") || 1;
  const search = sp.search ?? "";
  const chunkType = sp.chunk_type ?? "";

  const query = new URLSearchParams();
  if (search) query.set("search", search);
  if (chunkType) query.set("chunk_type", chunkType);
  query.set("page", String(page));
  query.set("page_size", "25");

  const [sourceResponse, chunksResponse] = await Promise.all([
    fetchFromApi(`/api/v1/knowledge/sources/${sourceId}`),
    fetchFromApi(`/api/v1/knowledge/sources/${sourceId}/chunks?${query.toString()}`),
  ]);

  if (sourceResponse.status === 404) {
    return (
      <div className="mx-auto max-w-3xl">
        <p className="text-sm text-red-600">Knowledge source not found.</p>
      </div>
    );
  }

  const source = (await sourceResponse.json()).data;
  const chunksPayload = await chunksResponse.json();
  const data: ChunkListResponse = chunksResponse.ok
    ? chunksPayload.data
    : { items: [], total: 0, offset: 0, limit: 25 };

  const totalPages = Math.max(1, Math.ceil(data.total / data.limit));

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6">
        <Link href={`/knowledge/${sourceId}`} className="text-xs font-medium text-accent hover:underline">
          ← Back to {source.title}
        </Link>
        <h1 className="mt-1 text-lg font-semibold text-charcoal">Chunks</h1>
        <p className="text-sm text-charcoal/50">{data.total} chunks indexed for this source</p>
      </div>

      <form className="mb-4 flex gap-3 text-sm" method="GET">
        <input
          type="text"
          name="search"
          defaultValue={search}
          placeholder="Search chunk content…"
          className="w-72 rounded-md border border-sand px-3 py-1.5"
        />
        <input
          type="text"
          name="chunk_type"
          defaultValue={chunkType}
          placeholder="Filter by chunk type"
          className="w-48 rounded-md border border-sand px-3 py-1.5"
        />
        <button type="submit" className="rounded-md border border-sand px-3 py-1.5 hover:bg-sand/40">
          Filter
        </button>
      </form>

      {!chunksResponse.ok && (
        <p className="text-sm text-red-600">{chunksPayload?.error?.message ?? "Could not load chunks."}</p>
      )}

      {chunksResponse.ok && data.items.length === 0 && (
        <p className="text-sm text-charcoal/50">No chunks match this filter.</p>
      )}

      <div className="space-y-3">
        {data.items.map((chunk) => (
          <div key={chunk.id} className="rounded-lg border border-sand bg-white p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-medium text-charcoal/50">
                #{chunk.chunk_index} · {chunk.chunk_key}
              </span>
              <div className="flex items-center gap-1.5">
                <StatusBadge value={chunk.chunk_type} />
                <StatusBadge value={chunk.status} />
                {!chunk.retrieval_enabled && <StatusBadge value="not retrievable" />}
              </div>
            </div>
            {chunk.heading_path && <p className="mb-1 text-xs text-charcoal/40">{chunk.heading_path}</p>}
            {chunk.section_title && <p className="mb-1 text-xs font-medium text-charcoal/60">{chunk.section_title}</p>}
            <p className="whitespace-pre-wrap text-sm text-charcoal/80">{chunk.content_raw}</p>
            <div className="mt-2 flex gap-2 text-xs text-charcoal/40">
              {chunk.page_number != null && <span>page {chunk.page_number}</span>}
              {chunk.token_count != null && <span>{chunk.token_count} tokens</span>}
            </div>
          </div>
        ))}
      </div>

      {totalPages > 1 && (
        <div className="mt-6 flex items-center justify-between text-sm">
          <Link
            href={`?${new URLSearchParams({ ...(search && { search }), ...(chunkType && { chunk_type: chunkType }), page: String(Math.max(1, page - 1)) }).toString()}`}
            aria-disabled={page <= 1}
            className={`rounded-md border border-sand px-3 py-1.5 ${page <= 1 ? "pointer-events-none opacity-40" : "hover:bg-sand/40"}`}
          >
            Previous
          </Link>
          <span className="text-charcoal/50">
            Page {page} of {totalPages}
          </span>
          <Link
            href={`?${new URLSearchParams({ ...(search && { search }), ...(chunkType && { chunk_type: chunkType }), page: String(Math.min(totalPages, page + 1)) }).toString()}`}
            aria-disabled={page >= totalPages}
            className={`rounded-md border border-sand px-3 py-1.5 ${page >= totalPages ? "pointer-events-none opacity-40" : "hover:bg-sand/40"}`}
          >
            Next
          </Link>
        </div>
      )}
    </div>
  );
}
