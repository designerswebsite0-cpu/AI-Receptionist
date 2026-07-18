"""HTML main-content extraction. Shared by uploaded HTML sources and the
website crawler (app.knowledge.website.crawler) — both need the exact same
"strip nav/footer/scripts, keep main/article" behavior per
WEBSITE_RAG_SYNC_POLICY.md and README_WEBSITE_INGESTION.md.
"""

from bs4 import BeautifulSoup

from app.knowledge.extraction.base import ExtractedContent

_STRIP_TAGS = ("nav", "footer", "script", "style", "noscript", "form")
_CONTENT_SELECTORS = ("main", "article")


def extract_html(content: bytes) -> ExtractedContent:
    soup = BeautifulSoup(content, "lxml")

    for tag_name in _STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    container = None
    for selector in _CONTENT_SELECTORS:
        container = soup.find(selector)
        if container is not None:
            break
    container = container or soup.body or soup

    text = container.get_text(separator="\n", strip=True)
    title = soup.title.get_text(strip=True) if soup.title else None
    headings = [h.get_text(strip=True) for h in container.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)]

    return ExtractedContent(
        raw_text=text,
        extraction_method="beautifulsoup4",
        word_count=len(text.split()),
        metadata={"title": title, "headings": headings},
    )
