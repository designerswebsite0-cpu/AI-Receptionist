import csv
import io

from app.errors import ValidationErrorApp
from app.knowledge.extraction.base import ExtractedContent

_MAX_ROWS = 50_000


def extract_csv(content: bytes) -> ExtractedContent:
    text = content.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) > _MAX_ROWS:
        raise ValidationErrorApp(f"CSV has {len(rows)} rows, exceeding the {_MAX_ROWS} limit")

    text_parts = [" | ".join(row) for row in rows]
    raw_text = "\n".join(text_parts)
    return ExtractedContent(
        raw_text=raw_text,
        extraction_method="csv",
        word_count=len(raw_text.split()),
        tables=[{"sheet_name": None, "rows": rows}],
    )
