"""Chunking strategies. Operates on already-normalized text — by the time
chunking runs, app.knowledge.normalization has already produced
knowledge_source_versions.normalized_text; a chunk's own content_raw and
content_normalized are therefore identical (both are slices of that
already-normalized text). The one "raw" record that matters — the
extractor's untouched output — is preserved once, at the version level,
not re-derived per chunk.
"""

import re

import tiktoken

from app.knowledge.chunking.base import Chunk

_ENCODING = tiktoken.get_encoding("cl100k_base")

_DEFAULT_MAX_TOKENS = 500
_DEFAULT_OVERLAP_TOKENS = 60

_FAQ_LINE_PATTERN = re.compile(r"^Q:\s", re.MULTILINE)
_FAQ_MIN_PAIRS_TO_DETECT = 3
_QA_PATTERN = re.compile(r"Q:\s*(.+?)\s*A:\s*(.+?)(?=\nQ:|\Z)", re.DOTALL)


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def chunk_generic_text(
    text: str,
    *,
    chunk_type: str = "generic",
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    overlap_tokens: int = _DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    """Paragraph-aware, token-bounded sliding window. Never splits a
    paragraph mid-sentence; carries the trailing paragraph(s) of one chunk
    forward into the next (up to overlap_tokens) so a fact split across a
    chunk boundary still has surrounding context in at least one chunk.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return []

    chunks: list[Chunk] = []
    current: list[str] = []
    current_tokens = 0
    index = 0

    def flush() -> None:
        nonlocal index
        if not current:
            return
        content = "\n\n".join(current)
        chunks.append(
            Chunk(
                chunk_type=chunk_type,
                chunk_index=index,
                content_raw=content,
                content_normalized=content,
                token_count=count_tokens(content),
            )
        )
        index += 1

    for paragraph in paragraphs:
        p_tokens = count_tokens(paragraph)

        if current and current_tokens + p_tokens > max_tokens:
            flush()
            overlap: list[str] = []
            overlap_sum = 0
            for para in reversed(current):
                t = count_tokens(para)
                if overlap_sum + t > overlap_tokens:
                    break
                overlap.insert(0, para)
                overlap_sum += t
            current = overlap
            current_tokens = overlap_sum

        current.append(paragraph)
        current_tokens += p_tokens

        # A single paragraph larger than the whole budget becomes its own
        # chunk immediately — otherwise it would block every future flush.
        if p_tokens > max_tokens:
            flush()
            current = []
            current_tokens = 0

    flush()
    return chunks


def chunk_faq_text(text: str) -> list[Chunk]:
    """Extracts every Q/A pair as its own chunk. Does not return the
    surrounding non-Q/A text — callers that need the remainder too (a
    document that has an FAQ section mixed in with other content, not a
    pure FAQ file) should use chunk_source, not this function directly.
    """
    chunks = []
    for index, match in enumerate(_QA_PATTERN.finditer(text)):
        question = " ".join(match.group(1).split())
        answer = " ".join(match.group(2).split())
        content = f"Q: {question}\nA: {answer}"
        chunks.append(
            Chunk(
                chunk_type="faq",
                chunk_index=index,
                content_raw=content,
                content_normalized=content,
                section_title=question,
                token_count=count_tokens(content),
                entity_metadata={"question": question, "answer": answer},
            )
        )
    return chunks


def chunk_table(tables: list[dict], *, chunk_type: str = "generic") -> list[Chunk]:
    """One chunk per data row — a room-rate spreadsheet's row for
    "Deluxe Suite, INR 25,000" is a far more useful retrieval unit than an
    arbitrary token-window slice of the sheet's flattened text."""
    chunks = []
    index = 0
    for table in tables:
        rows = table.get("rows") or []
        if not rows:
            continue
        header = rows[0]
        for row in rows[1:]:
            if not any(str(cell).strip() for cell in row):
                continue
            pairs = [f"{h}: {v}" for h, v in zip(header, row, strict=False) if str(h).strip() and str(v).strip()]
            if not pairs:
                continue
            content = "\n".join(pairs)
            entity_metadata = {str(h): v for h, v in zip(header, row, strict=False) if str(h).strip()}
            chunks.append(
                Chunk(
                    chunk_type=chunk_type,
                    chunk_index=index,
                    content_raw=content,
                    content_normalized=content,
                    section_title=table.get("sheet_name"),
                    token_count=count_tokens(content),
                    entity_metadata=entity_metadata,
                )
            )
            index += 1
    return chunks


def _looks_like_faq(text: str) -> bool:
    return len(_FAQ_LINE_PATTERN.findall(text)) >= _FAQ_MIN_PAIRS_TO_DETECT


def chunk_source(
    *, normalized_text: str, tables: list[dict] | None = None, chunk_type_hint: str | None = None
) -> list[Chunk]:
    if tables:
        return chunk_table(tables, chunk_type=chunk_type_hint or "generic")
    if not _looks_like_faq(normalized_text):
        return chunk_generic_text(normalized_text, chunk_type=chunk_type_hint or "generic")

    # Mixed-content documents (e.g. RKPR_Resort_Restaurant_Menu_Full_2026.pdf,
    # whose menu/pricing sections are followed by a "Frequently Asked
    # Questions" appendix) must not have their non-FAQ content silently
    # discarded just because a Q&A section exists somewhere in the text —
    # confirmed as a real bug against that exact file before this fix:
    # the whole 7-page menu collapsed into 5 FAQ-only chunks. Extract the
    # FAQ pairs, then chunk whatever text is left over (with the Q/A spans
    # removed) using the generic strategy.
    faq_matches = list(_QA_PATTERN.finditer(normalized_text))
    faq_chunks = chunk_faq_text(normalized_text)

    remainder_parts = []
    last_end = 0
    for match in faq_matches:
        remainder_parts.append(normalized_text[last_end : match.start()])
        last_end = match.end()
    remainder_parts.append(normalized_text[last_end:])
    remainder_text = "\n\n".join(part.strip() for part in remainder_parts if part.strip())

    generic_chunks = (
        chunk_generic_text(remainder_text, chunk_type=chunk_type_hint or "generic") if remainder_text else []
    )
    return faq_chunks + generic_chunks
