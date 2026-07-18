"""Text normalization — produces knowledge_source_versions.normalized_text
from raw_text. Both are stored (migration 0012's docstring): raw_text
stays a faithful record of what the extractor produced, normalized_text is
what chunking/embedding actually operate on.
"""

import re
import unicodedata

_MULTI_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_WHITESPACE = re.compile(r"[ \t]+\n")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
# Common OCR/PDF-extraction artifacts: soft hyphens, form-feed page breaks,
# zero-width characters that survive text extraction but carry no meaning.
_STRIP_CHARS = "­​‌‍﻿\x0c"


def normalize_text(raw_text: str) -> str:
    text = unicodedata.normalize("NFKC", raw_text)
    for char in _STRIP_CHARS:
        text = text.replace(char, "")
    text = _TRAILING_WHITESPACE.sub("\n", text)
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_BLANK_LINES.sub("\n\n", text)
    return text.strip()


def strip_repeated_lines(text: str, *, min_repeats: int = 3) -> str:
    """Removes lines that repeat verbatim often enough to be running
    headers/footers (e.g. a resort name printed on every page of a PDF) —
    applied after normalize_text, before chunking, so a header line
    doesn't get embedded as if it were content on every single chunk."""
    lines = text.split("\n")
    counts: dict[str, int] = {}
    for line in lines:
        stripped = line.strip()
        if stripped:
            counts[stripped] = counts.get(stripped, 0) + 1

    repeated = {line for line, count in counts.items() if count >= min_repeats and len(line) < 120}
    if not repeated:
        return text

    kept = [line for line in lines if line.strip() not in repeated]
    return _MULTI_BLANK_LINES.sub("\n\n", "\n".join(kept)).strip()
