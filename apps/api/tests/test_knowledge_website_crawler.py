"""Pure-logic tests for app.knowledge.website.crawler's URL handling — no
network access required. These specifically encode the two real bugs
confirmed live on the RKPR website before this module was written:
robots.txt's `Sitemap:` directive and every sitemap `<loc>` point at
http://localhost:3000 instead of the real domain.
"""

from app.knowledge.website.crawler import canonicalize_url, is_allowed_path, rebase_url
from app.knowledge.website.seed import WebsiteCrawlSeed


def _seed(**overrides) -> WebsiteCrawlSeed:
    defaults = dict(
        source_id="WEB-RKPR-001",
        name="RKPR Resort Official Website",
        base_url="https://rkpr-website.vercel.app",
        sitemap_url="https://rkpr-website.vercel.app/sitemap.xml",
        robots_url="https://rkpr-website.vercel.app/robots.txt",
        allowed_path_prefixes=["/stay", "/dining", "/faq"],
        explicit_allow=["/"],
        excluded_path_prefixes=["/api", "/dev", "/_next"],
    )
    defaults.update(overrides)
    return WebsiteCrawlSeed(**defaults)


def test_seed_from_dict_matches_real_website_crawl_seed_shape():
    data = {
        "source_id": "WEB-RKPR-001",
        "name": "RKPR Resort Official Website",
        "base_url": "https://rkpr-website.vercel.app/",
        "sitemap_url": "https://rkpr-website.vercel.app/sitemap.xml",
        "robots_url": "https://rkpr-website.vercel.app/robots.txt",
        "allowed_path_prefixes": ["/stay", "/dining"],
        "explicit_allow": ["/"],
        "excluded_path_prefixes": ["/api", "/dev", "/_next"],
        "exclude_query_parameters": True,
        "canonicalize_urls": True,
        "source_priority": "normal",
    }
    seed = WebsiteCrawlSeed.from_dict(data)
    assert seed.base_url == "https://rkpr-website.vercel.app"  # trailing slash stripped


def test_rebase_url_replaces_wrong_host_with_configured_base_url():
    # This is the exact bug confirmed live: sitemap.xml's <loc> values all
    # say http://localhost:3000/... — only the path is trustworthy.
    result = rebase_url("http://localhost:3000/stay", base_url="https://rkpr-website.vercel.app")
    assert result == "https://rkpr-website.vercel.app/stay"


def test_rebase_url_preserves_query_string():
    result = rebase_url("http://localhost:3000/offers?utm=x", base_url="https://rkpr-website.vercel.app")
    assert result == "https://rkpr-website.vercel.app/offers?utm=x"


def test_rebase_url_handles_root_path():
    result = rebase_url("http://localhost:3000", base_url="https://rkpr-website.vercel.app")
    assert result == "https://rkpr-website.vercel.app/"


def test_canonicalize_url_strips_trailing_slash():
    assert canonicalize_url("https://example.com/stay/", exclude_query_parameters=True) == "https://example.com/stay"


def test_canonicalize_url_keeps_root_slash():
    assert canonicalize_url("https://example.com/", exclude_query_parameters=True) == "https://example.com/"


def test_canonicalize_url_strips_query_when_configured():
    result = canonicalize_url("https://example.com/offers?ref=email", exclude_query_parameters=True)
    assert result == "https://example.com/offers"


def test_canonicalize_url_keeps_query_when_not_excluded():
    result = canonicalize_url("https://example.com/offers?ref=email", exclude_query_parameters=False)
    assert "ref=email" in result


def test_is_allowed_path_accepts_explicit_root():
    seed = _seed()
    assert is_allowed_path("/", seed) is True


def test_is_allowed_path_accepts_configured_prefix():
    seed = _seed()
    assert is_allowed_path("/stay/garden-deluxe-room", seed) is True


def test_is_allowed_path_rejects_excluded_prefix_even_if_also_allowed():
    seed = _seed(allowed_path_prefixes=["/api/docs"], excluded_path_prefixes=["/api"])
    assert is_allowed_path("/api/docs", seed) is False


def test_is_allowed_path_rejects_unlisted_path():
    seed = _seed()
    assert is_allowed_path("/some-random-unlisted-path", seed) is False
