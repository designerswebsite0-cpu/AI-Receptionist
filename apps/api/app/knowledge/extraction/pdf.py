"""PDF text extraction + per-page OCR-required detection.

Density threshold, not "any page with zero text": a page can legitimately
have sparse text (a cover page, a page that's mostly a photo with a short
caption) without needing OCR. The threshold catches pages that are
image-only scans wearing a PDF wrapper — exactly the RKPR_RAG_FINAL_DOCS/
03_OCR_TESTS/ cases this pipeline must handle correctly.
"""

import fitz  # PyMuPDF

from app.knowledge.extraction.base import ExtractedContent

# Empirically chosen: a normal text page has on the order of 1500-3000
# characters per (72dpi) letter-size page (~500,000 sq-pt area), i.e.
# roughly 0.003-0.006 chars/sq-pt. 0.001 comfortably separates "genuinely
# sparse text page" from "no extractable text at all" (scanned image).
_MIN_TEXT_DENSITY = 0.001


def extract_pdf(content: bytes) -> ExtractedContent:
    with fitz.open(stream=content, filetype="pdf") as doc:
        page_texts: list[str] = []
        pages_needing_ocr: list[int] = []
        for index, page in enumerate(doc, start=1):
            text = page.get_text()
            page_texts.append(text)
            area = page.rect.width * page.rect.height or 1.0
            if (len(text.strip()) / area) < _MIN_TEXT_DENSITY:
                pages_needing_ocr.append(index)

        raw_text = "\n\n".join(page_texts)
        return ExtractedContent(
            raw_text=raw_text,
            extraction_method="pymupdf",
            page_count=doc.page_count,
            word_count=len(raw_text.split()),
            pages_needing_ocr=pages_needing_ocr,
        )


def render_page_to_png(content: bytes, page_number: int, *, zoom: float = 2.0) -> bytes:
    """Rasterizes one page for OCR. zoom=2.0 roughly doubles the effective
    DPI (72 -> ~144), which materially improves Tesseract accuracy over
    the default render resolution at negligible extra cost for a
    single-page render."""
    with fitz.open(stream=content, filetype="pdf") as doc:
        page = doc[page_number - 1]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return pixmap.tobytes("png")
