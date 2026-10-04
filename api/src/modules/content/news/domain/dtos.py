from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, HttpUrl


class NewsSource(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    feed_url: HttpUrl
    allowed_hosts: set[str] = Field(min_length=1)
    topics: set[str] = Field(min_length=1)
    enabled: bool = False
    kind: Literal["rss", "hackernews"] = "rss"
    external_articles: bool = False
    default_topics: list[str] = Field(default_factory=list)
    search_page_size: int = Field(default=10, ge=1, le=50)


class ArticleInput(BaseModel):
    source_id: str
    url: str
    title: str
    published_at: datetime | None
    body: str
    fetched_at: datetime
    truncated: bool = False


class CollectNews(BaseModel):
    topic: str = Field(min_length=1, max_length=64)
    since: AwareDatetime
    limit: int = Field(default=3, ge=1, le=3)


class ArticleEvidence(BaseModel):
    id: int
    source_id: str
    url: str
    title: str
    published_at: datetime | None
    fetched_at: datetime
    body: str
    truncated: bool


class NewsDraftItem(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=450)
    evidence_ids: list[int] = Field(min_length=1, max_length=3)


class NewsDraft(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    items: list[NewsDraftItem] = Field(min_length=1, max_length=2)
    editorial_note: str | None = Field(default=None, max_length=200)
