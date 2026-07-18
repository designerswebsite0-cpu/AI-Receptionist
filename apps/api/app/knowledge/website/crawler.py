"""Website crawler: sitemap-then-links discovery, robots.txt respect,
allow/deny filtering, canonicalization, main-content extraction.

The URL-rebasing logic exists because of two confirmed real bugs on the
live site (checked directly via curl before this module was written, not
assumed from the packaged docs): robots.txt's `Sitemap:` directive and
every `<loc>` in sitemap.xml point at `http://localhost:3000` — a
deployment misconfiguration on the resort's side, not a crawler bug to
work around defensively "just in case". Only the *path* (and query
string, if kept) from each `<loc>` is trustworthy; the real host always
comes from the seed config's `base_url`.
"""

import hashlib
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib import robotparser
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from app.knowledge.extraction.html import extract_html
from app.knowledge.website.seed import WebsiteCrawlSeed

_TIMEOUT_SECONDS = 15.0
_USER_AGENT = "RKPR-Knowledge-Crawler/1.0"


@dataclass
class CrawledPage:
    url: str
    canonical_url: str
    http_status: int
    title: str | None
    headings: list[str] = field(default_factory=list)
    content_text: str = ""
    content_hash: str = ""
    fetched_at: str = ""
    error: str | None = None


def rebase_url(raw_url: str, *, base_url: str) -> str:
    parsed = urlsplit(raw_url)
    path = parsed.path or "/"
    rebased = urljoin(base_url + "/", path.lstrip("/"))
    if parsed.query:
        rebased = f"{rebased}?{parsed.query}"
    return rebased


def canonicalize_url(url: str, *, exclude_query_parameters: bool) -> str:
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/") or "/"
    query = "" if exclude_query_parameters else parsed.query
    return urlunsplit((parsed.scheme, parsed.netloc, path, query, ""))


def is_allowed_path(path: str, seed: WebsiteCrawlSeed) -> bool:
    if any(path.startswith(prefix) for prefix in seed.excluded_path_prefixes):
        return False
    if path in seed.explicit_allow:
        return True
    return any(path.startswith(prefix) for prefix in seed.allowed_path_prefixes)


async def _fetch_robots(client: httpx.AsyncClient, robots_url: str) -> robotparser.RobotFileParser:
    parser = robotparser.RobotFileParser()
    try:
        response = await client.get(robots_url, timeout=_TIMEOUT_SECONDS)
        parser.parse(response.text.splitlines() if response.status_code == 200 else [])
    except httpx.HTTPError:
        parser.parse([])  # unreachable robots.txt -> permissive default, not a crawl-blocking failure
    return parser


async def _fetch_sitemap_locs(client: httpx.AsyncClient, sitemap_url: str) -> list[str]:
    response = await client.get(sitemap_url, timeout=_TIMEOUT_SECONDS)
    response.raise_for_status()
    root = ElementTree.fromstring(response.text)
    return [element.text for element in root.iter() if element.tag.endswith("loc") and element.text]


async def discover_urls(client: httpx.AsyncClient, seed: WebsiteCrawlSeed) -> list[str]:
    raw_locs = await _fetch_sitemap_locs(client, seed.sitemap_url)
    robots = await _fetch_robots(client, seed.robots_url)

    discovered: list[str] = []
    seen: set[str] = set()
    for raw in raw_locs:
        rebased = rebase_url(raw, base_url=seed.base_url)
        path = urlsplit(rebased).path or "/"

        if not is_allowed_path(path, seed):
            continue
        if not robots.can_fetch(_USER_AGENT, rebased):
            continue

        url = (
            canonicalize_url(rebased, exclude_query_parameters=seed.exclude_query_parameters)
            if seed.canonicalize_urls
            else rebased
        )
        if url in seen:
            continue
        seen.add(url)
        discovered.append(url)
    return discovered


async def fetch_page(client: httpx.AsyncClient, url: str) -> CrawledPage:
    fetched_at = datetime.now(UTC).isoformat()
    try:
        response = await client.get(url, timeout=_TIMEOUT_SECONDS, follow_redirects=True)
    except httpx.HTTPError as exc:
        return CrawledPage(
            url=url, canonical_url=url, http_status=0, title=None, fetched_at=fetched_at, error=str(exc)
        )

    if response.status_code != 200:
        return CrawledPage(
            url=url,
            canonical_url=str(response.url),
            http_status=response.status_code,
            title=None,
            fetched_at=fetched_at,
        )

    extracted = extract_html(response.content)
    content_hash = hashlib.sha256(extracted.raw_text.encode("utf-8")).hexdigest()
    return CrawledPage(
        url=url,
        canonical_url=str(response.url),
        http_status=response.status_code,
        title=extracted.metadata.get("title"),
        headings=extracted.metadata.get("headings", []),
        content_text=extracted.raw_text,
        content_hash=content_hash,
        fetched_at=fetched_at,
    )


async def crawl(seed: WebsiteCrawlSeed) -> list[CrawledPage]:
    async with httpx.AsyncClient(headers={"User-Agent": _USER_AGENT}) as client:
        urls = await discover_urls(client, seed)
        return [await fetch_page(client, url) for url in urls]
