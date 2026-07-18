"""Loads website_crawl_seed.json (or an equivalent dict) into a typed
config the crawler operates on. See
RKPR_RAG_FINAL_DOCS/01_GUEST_KNOWLEDGE/Website/website_crawl_seed.json for
the real file this schema was built from.
"""

from dataclasses import dataclass, field


@dataclass
class WebsiteCrawlSeed:
    source_id: str
    name: str
    base_url: str
    sitemap_url: str
    robots_url: str
    allowed_path_prefixes: list[str] = field(default_factory=list)
    explicit_allow: list[str] = field(default_factory=list)
    excluded_path_prefixes: list[str] = field(default_factory=list)
    exclude_query_parameters: bool = True
    canonicalize_urls: bool = True
    source_priority: str = "normal"

    @classmethod
    def from_dict(cls, data: dict) -> "WebsiteCrawlSeed":
        return cls(
            source_id=data["source_id"],
            name=data["name"],
            base_url=data["base_url"].rstrip("/"),
            sitemap_url=data["sitemap_url"],
            robots_url=data["robots_url"],
            allowed_path_prefixes=list(data.get("allowed_path_prefixes", [])),
            explicit_allow=list(data.get("explicit_allow", [])),
            excluded_path_prefixes=list(data.get("excluded_path_prefixes", [])),
            exclude_query_parameters=bool(data.get("exclude_query_parameters", True)),
            canonicalize_urls=bool(data.get("canonicalize_urls", True)),
            source_priority=data.get("source_priority", "normal"),
        )
