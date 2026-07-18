import hashlib
from dataclasses import dataclass, field


@dataclass
class Chunk:
    chunk_type: str
    chunk_index: int
    content_raw: str
    content_normalized: str
    section_title: str | None = None
    heading_path: str | None = None
    page_number: int | None = None
    token_count: int | None = None
    entity_metadata: dict = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content_normalized.encode("utf-8")).hexdigest()

    @property
    def chunk_key(self) -> str:
        """Deterministic across re-ingestion runs of an unchanged source:
        same chunk_type + position + content always produces the same
        key, so app.knowledge.embeddings can detect "this exact chunk
        already exists with an embedding" and skip re-embedding it. A
        content edit changes the hash (and therefore the key), which is
        exactly the signal the embedding step needs to re-embed only what
        changed — see IMPLEMENTATION_PLAN.md's incremental-embedding rule.
        """
        return f"{self.chunk_type}:{self.chunk_index:04d}:{self.content_hash[:16]}"
