from dataclasses import dataclass, field


@dataclass
class ExtractedContent:
    """Common output shape every format-specific extractor produces.
    Normalization (whitespace/unicode/header-footer cleanup) happens
    separately in app.knowledge.normalization — extractors return text as
    the source library gave it to them, unmodified, so raw_text stays a
    faithful record of what was actually extracted.
    """

    raw_text: str
    extraction_method: str
    page_count: int | None = None
    word_count: int = 0
    # 1-indexed page numbers whose extracted text is too sparse to be
    # trustworthy on its own — the ingestion pipeline routes these through
    # OCR (app.knowledge.ocr) rather than trusting a near-empty extraction.
    pages_needing_ocr: list[int] = field(default_factory=list)
    # Structured rows for spreadsheet/CSV sources, consumed by the
    # chunking strategies that build room_rate/menu_item/etc. chunks
    # directly from tabular data rather than from raw_text.
    tables: list[dict] | None = None
    metadata: dict = field(default_factory=dict)
