"""Integration test for app.knowledge.website.service.run_crawl — requires
a reachable Postgres with pgvector (see conftest.db_engine); skips
cleanly when none is available.

Uses httpx.MockTransport to simulate the website rather than hitting the
live site: deterministic, offline, and still reproduces the real bug this
crawler was built around (sitemap <loc> values pointing at the wrong
host). The actual live RKPR site was crawled manually during development
(49 URLs discovered, 40 fetched successfully, 9 real 404s on the site's
own sitemap) — see docs/phase-3/PHASE_3_COMPLETION_REPORT.md.
"""

from unittest.mock import patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge import repository, service
from app.knowledge.embeddings import MockEmbeddingProvider
from app.knowledge.schemas import SourceRegisterRequest
from app.knowledge.website.seed import WebsiteCrawlSeed
from app.knowledge.website.service import run_crawl

_RealAsyncClient = httpx.AsyncClient  # captured before any patching, to avoid self-referential recursion

_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>http://localhost:3000</loc></url>
<url><loc>http://localhost:3000/stay</loc></url>
<url><loc>http://localhost:3000/faq</loc></url>
</urlset>"""

_ROBOTS_TXT = "User-Agent: *\nAllow: /\nSitemap: http://localhost:3000/sitemap.xml\n"

_PAGE_HTML = """<!DOCTYPE html><html><head><title>{title}</title></head>
<body><nav>Site nav</nav><main><h1>{heading}</h1><p>{body}</p></main>
<footer>Copyright</footer></body></html>"""


def _fake_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url.endswith("/sitemap.xml"):
        return httpx.Response(200, text=_SITEMAP_XML)
    if url.endswith("/robots.txt"):
        return httpx.Response(200, text=_ROBOTS_TXT)
    if url == "https://rkpr-website.vercel.app/" or url == "https://rkpr-website.vercel.app":
        return httpx.Response(200, text=_PAGE_HTML.format(title="Home", heading="Welcome", body="Resort homepage."))
    if url == "https://rkpr-website.vercel.app/stay":
        return httpx.Response(
            200, text=_PAGE_HTML.format(title="Stay", heading="Our Rooms", body="Deluxe suites available.")
        )
    if url == "https://rkpr-website.vercel.app/faq":
        return httpx.Response(404, text="Not Found")
    return httpx.Response(404, text="Not Found")


def _seed() -> WebsiteCrawlSeed:
    return WebsiteCrawlSeed(
        source_id="WEB-TEST-001",
        name="Test Resort Website",
        base_url="https://rkpr-website.vercel.app",
        sitemap_url="https://rkpr-website.vercel.app/sitemap.xml",
        robots_url="https://rkpr-website.vercel.app/robots.txt",
        allowed_path_prefixes=["/stay", "/faq"],
        explicit_allow=["/"],
        excluded_path_prefixes=["/api", "/dev", "/_next"],
    )


@pytest.mark.asyncio
async def test_run_crawl_persists_pages_as_chunks_and_handles_real_404(db_session: AsyncSession):
    source = await service.register_source(
        db_session,
        body=SourceRegisterRequest(
            source_id="WEB-TEST-001", title="Test Resort Website", source_type="website", visibility="guest"
        ),
        actor_user_id=None,
    )

    mock_transport = httpx.MockTransport(_fake_handler)
    with patch("httpx.AsyncClient", lambda **kwargs: _RealAsyncClient(transport=mock_transport, **kwargs)):
        crawl_run = await run_crawl(
            db_session, source=source, seed=_seed(), embedding_provider=MockEmbeddingProvider()
        )

    assert crawl_run.pages_discovered == 3
    assert crawl_run.pages_crawled == 2  # home + /stay succeeded
    assert crawl_run.pages_failed == 1  # /faq returned a real 404
    assert crawl_run.run_status == "completed"
    assert any(entry["http_status"] == 404 for entry in crawl_run.crawl_summary)

    chunks = await repository.list_chunks_for_source(db_session, source.id)
    assert len(chunks) >= 2
    assert all(chunk.chunk_type == "website_page" for chunk in chunks)
    assert all(
        chunk.entity_metadata.get("page_url", "").startswith("https://rkpr-website.vercel.app") for chunk in chunks
    )
    assert all(chunk.embedding is not None for chunk in chunks)


@pytest.mark.asyncio
async def test_run_crawl_second_run_detects_unchanged_pages(db_session: AsyncSession):
    source = await service.register_source(
        db_session,
        body=SourceRegisterRequest(
            source_id="WEB-TEST-002", title="Test Resort Website 2", source_type="website", visibility="guest"
        ),
        actor_user_id=None,
    )
    mock_transport = httpx.MockTransport(_fake_handler)

    with patch("httpx.AsyncClient", lambda **kwargs: _RealAsyncClient(transport=mock_transport, **kwargs)):
        provider = MockEmbeddingProvider()
        await run_crawl(db_session, source=source, seed=_seed(), embedding_provider=provider)
        second = await run_crawl(db_session, source=source, seed=_seed(), embedding_provider=provider)

    # Identical content on both runs -> zero pages counted as "changed".
    assert second.pages_changed == 0
