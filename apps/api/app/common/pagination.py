from pydantic import BaseModel, Field


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

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
