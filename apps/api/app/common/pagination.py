from pydantic import BaseModel, Field


class PageParams(BaseModel):
    # 200, not 100: matches the highest page_size any endpoint's own Query()
    # declares (conversations/{id}/messages, audit/logs, knowledge chunks
    # all use le=200) — this model's own cap must never be stricter than
    # theirs, or a value FastAPI's own parameter validation already
    # accepted raises an unhandled, unrelated-looking 500 the moment this
    # class is constructed inside the endpoint body (see the 2026-07-24
    # "conversation thread shows no messages" incident: thread.tsx has
    # always requested page_size=200, which this cap silently 500'd on).
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


def build_page_meta(params: PageParams, total: int) -> PageMeta:
    total_pages = (total + params.page_size - 1) // params.page_size if total else 0
    return PageMeta(page=params.page, page_size=params.page_size, total=total, total_pages=total_pages)
