"""Ties extraction -> normalization -> chunking -> embedding into one
pipeline stage, shared by the governance importer (bulk RKPR import) and
the future upload API endpoint (Step 10) so both go through identical
logic rather than each reimplementing chunk diffing/incremental embedding.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge import repository
from app.knowledge.chunking.base import Chunk
from app.knowledge.chunking.strategies import chunk_source
from app.knowledge.constants import CHUNK_TYPES
from app.knowledge.embeddings import EmbeddingProvider, embed_texts
from app.knowledge.extraction.base import ExtractedContent
from app.knowledge.models import KnowledgeChunk, KnowledgeSource, KnowledgeSourceVersion
from app.knowledge.normalization import normalize_text, strip_repeated_lines


@dataclass
class IndexResult:
    chunks_created: int
    chunks_updated: int
    chunks_deleted: int
    chunks_embedded: int


async def index_source_version(
    db: AsyncSession,
    *,
    source: KnowledgeSource,
    version: KnowledgeSourceVersion,
    extracted: ExtractedContent,
    provider: EmbeddingProvider,
    chunk_type_hint: str | None = None,
) -> IndexResult:
    normalized = strip_repeated_lines(normalize_text(extracted.raw_text))

    version.raw_text = extracted.raw_text
    version.normalized_text = normalized
    version.page_count = extracted.page_count
    version.word_count = extracted.word_count
    version.extraction_method = extracted.extraction_method

    # Both governance-importer call sites pass source.category explicitly
    # as chunk_type_hint — a free-text register/folder label (e.g.
    # "Dining", "Rooms") for humans, not the fixed CHUNK_TYPES vocabulary
    # the knowledge_chunks.chunk_type column's CHECK constraint enforces.
    # Validate whatever hint is ultimately in play (explicit argument or
    # source.category) rather than only the fallback branch, since an
    # explicit-but-invalid value would otherwise win over any default.
    # chunk_source's own per-section detection (e.g. Q&A -> "faq") already
    # overrides this where it can tell more specifically; "generic" is
    # always a safe, valid fallback for whatever it can't.
    resolved_hint = chunk_type_hint or source.category
    validated_hint = resolved_hint if resolved_hint in CHUNK_TYPES else "generic"
    new_chunks = chunk_source(normalized_text=normalized, tables=extracted.tables, chunk_type_hint=validated_hint)

    return await persist_chunks(db, source=source, version=version, chunks=new_chunks, provider=provider)


async def persist_chunks(
    db: AsyncSession,
    *,
    source: KnowledgeSource,
    version: KnowledgeSourceVersion,
    chunks: list[Chunk],
    provider: EmbeddingProvider,
) -> IndexResult:
    """Diffs a set of already-built Chunk objects against what's currently
    stored for this source and embeds only what changed. Factored out of
    index_source_version so the website crawler (which builds chunks
    per-page, each tagged with its own page_url in entity_metadata, rather
    than from one extracted document) can reuse the identical diff/embed
    logic instead of duplicating it.
    """
    existing_chunks = await repository.list_chunks_for_source(db, source.id)
    existing_by_key = {row.chunk_key: row for row in existing_chunks}
    new_by_key: dict[str, Chunk] = {chunk.chunk_key: chunk for chunk in chunks}

    created = 0
    updated = 0
    to_embed: list[tuple[KnowledgeChunk, str]] = []

    for key, chunk in new_by_key.items():
        row = existing_by_key.get(key)
        if row is None:
            row = KnowledgeChunk(
                id=uuid.uuid4(),
                source_id=source.id,
                version_id=version.id,
                chunk_key=key,
                chunk_type=chunk.chunk_type,
                chunk_index=chunk.chunk_index,
                content_raw=chunk.content_raw,
                content_normalized=chunk.content_normalized,
                content_hash=chunk.content_hash,
                section_title=chunk.section_title,
                heading_path=chunk.heading_path,
                page_number=chunk.page_number,
                token_count=chunk.token_count,
                entity_metadata=chunk.entity_metadata,
                visibility=source.visibility,
                source_priority=source.source_priority,
                authoritative=source.authoritative,
                retrieval_enabled=source.retrieval_enabled,
                effective_date=source.effective_date,
                expiry_date=source.expiry_date,
                status="active",
            )
            db.add(row)
            created += 1
        else:
            row.version_id = version.id
            updated += 1

        to_embed.append((row, chunk.content_normalized))

    # A chunk_key that existed before but isn't in this run's output means
    # its content changed or the source shrank — the old row is stale and
    # must not linger as a retrievable duplicate of superseded content.
    stale_ids = [row.id for key, row in existing_by_key.items() if key not in new_by_key]
    await repository.delete_chunks_by_ids(db, stale_ids)

    # Incremental embedding: only chunks missing an embedding, or embedded
    # by a different model than the one in use now, are re-embedded.
    needing_embedding = [
        (row, text) for row, text in to_embed if row.embedding is None or row.embedding_model != provider.model
    ]
    if needing_embedding:
        vectors = await embed_texts(provider, [text for _, text in needing_embedding])
        for (row, _), result in zip(needing_embedding, vectors, strict=True):
            row.embedding = result.vector
            row.embedding_model = result.model

    await db.flush()

    return IndexResult(
        chunks_created=created,
        chunks_updated=updated,
        chunks_deleted=len(stale_ids),
        chunks_embedded=len(needing_embedding),
    )
