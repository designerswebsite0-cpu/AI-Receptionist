"""Persists a website crawl: one WebsiteCrawlRun row per execution, one
KnowledgeSourceVersion representing the crawl snapshot, and chunks tagged
per-page (entity_metadata carries page_url/page_title, since a website
source's chunks span many distinct pages rather than one document).
"""

import hashlib
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge import repository, service
from app.knowledge.chunking.strategies import chunk_generic_text
from app.knowledge.embeddings import EmbeddingProvider
from app.knowledge.indexing import persist_chunks
from app.knowledge.models import KnowledgeSource, WebsiteCrawlRun
from app.knowledge.normalization import normalize_text, strip_repeated_lines
from app.knowledge.website.crawler import CrawledPage, crawl
from app.knowledge.website.seed import WebsiteCrawlSeed


def _build_page_chunks(pages: list[CrawledPage]):
    all_chunks = []
    running_index = 0
    for page in pages:
        if page.http_status != 200 or not page.content_text.strip():
            continue
        normalized = strip_repeated_lines(normalize_text(page.content_text))
        page_chunks = chunk_generic_text(normalized, chunk_type="website_page")
        for chunk in page_chunks:
            chunk.chunk_index = running_index
            running_index += 1
            chunk.section_title = chunk.section_title or page.title
            chunk.entity_metadata = {
                **chunk.entity_metadata,
                "page_url": page.canonical_url,
                "page_title": page.title,
            }
        all_chunks.extend(page_chunks)
    return all_chunks


async def run_crawl(
    db: AsyncSession, *, source: KnowledgeSource, seed: WebsiteCrawlSeed, embedding_provider: EmbeddingProvider
) -> WebsiteCrawlRun:
    crawl_run = await repository.create_crawl_run(db, source_id=source.id)
    previous_run = await repository.get_latest_crawl_run(db, source.id)
    previous_hashes = (
        {entry["canonical_url"]: entry["content_hash"] for entry in previous_run.crawl_summary}
        if previous_run
        else {}
    )

    pages = await crawl(seed)
    ok_pages = [p for p in pages if p.http_status == 200]

    combined = "|".join(sorted(p.content_hash for p in ok_pages))
    checksum = hashlib.sha256(combined.encode("utf-8")).hexdigest() if combined else hashlib.sha256(b"").hexdigest()

    version = await service.record_source_version(
        db, source_id=source.id, checksum_sha256=checksum, storage_path=None, actor_user_id=None
    )
    version.page_count = len(ok_pages)
    version.word_count = sum(len(p.content_text.split()) for p in ok_pages)
    version.extraction_method = "website-crawl"

    chunks = _build_page_chunks(pages)
    await persist_chunks(db, source=source, version=version, chunks=chunks, provider=embedding_provider)

    pages_changed = sum(
        1 for p in ok_pages if previous_hashes.get(p.canonical_url) != p.content_hash
    )

    crawl_run.pages_discovered = len(pages)
    crawl_run.pages_crawled = len(ok_pages)
    crawl_run.pages_changed = pages_changed
    crawl_run.pages_failed = len(pages) - len(ok_pages)
    crawl_run.run_status = "completed"
    crawl_run.completed_at = datetime.now(UTC)
    crawl_run.crawl_summary = [
        {
            "url": p.url,
            "canonical_url": p.canonical_url,
            "http_status": p.http_status,
            "content_hash": p.content_hash,
            "error": p.error,
        }
        for p in pages
    ]

    version.processing_status = "completed"
    source.processing_status = "completed"

    await db.commit()
    await db.refresh(crawl_run)
    return crawl_run
