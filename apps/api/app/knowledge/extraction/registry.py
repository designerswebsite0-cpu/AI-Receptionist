from collections.abc import Callable

from app.errors import ValidationErrorApp
from app.knowledge.extraction.base import ExtractedContent
from app.knowledge.extraction.csv_format import extract_csv
from app.knowledge.extraction.docx import extract_docx
from app.knowledge.extraction.html import extract_html
from app.knowledge.extraction.pdf import extract_pdf
from app.knowledge.extraction.plain_text import extract_txt
from app.knowledge.extraction.xlsx import extract_xlsx

_EXTRACTORS: dict[str, Callable[[bytes], ExtractedContent]] = {
    "pdf": extract_pdf,
    "docx": extract_docx,
    "xlsx": extract_xlsx,
    "csv": extract_csv,
    "html": extract_html,
    "txt": extract_txt,
}


def extract(file_format: str, content: bytes) -> ExtractedContent:
    extractor = _EXTRACTORS.get(file_format)
    if extractor is None:
        raise ValidationErrorApp(f"No text extractor registered for format '{file_format}'")
    return extractor(content)
