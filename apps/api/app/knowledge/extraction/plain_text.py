from app.knowledge.extraction.base import ExtractedContent


def extract_txt(content: bytes) -> ExtractedContent:
    text = content.decode("utf-8")
    return ExtractedContent(
        raw_text=text,
        extraction_method="plain-text",
        word_count=len(text.split()),
    )
