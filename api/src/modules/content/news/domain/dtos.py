import unicodedata
from datetime import datetime
from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


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
    exclude_published: bool = False
    excluded_url_hashes: set[str] = Field(default_factory=set)


class ArticleEvidence(BaseModel):
    id: int
    source_id: str
    url: str
    title: str
    published_at: datetime | None
    fetched_at: datetime
    body: str
    truncated: bool


def validate_news_summary(summary: str) -> None:
    ending = summary.rstrip()
    while ending and (
        unicodedata.category(ending[-1])
        in {"So", "Sk", "Mn", "Me", "Cf", "Zs", "Pe", "Pf"}
        or ending[-1] in "\"'»"
    ):
        ending = ending[:-1].rstrip()
    if not ending.endswith((".", "!", "?", "؟", "…")):
        raise ValueError(
            "Finish each summary with a complete sentence and punctuation. "
            "Rewrite it shorter; never crop a sentence to fit the limit."
        )


class NewsDraftItem(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(
        min_length=1,
        max_length=450,
        description=(
            "Two or three complete spoken sentences, ending with "
            "punctuation. Never crop a sentence."
        ),
    )
    evidence_ids: list[int] = Field(min_length=1, max_length=3)

    @field_validator("summary")
    @classmethod
    def finished_summary(cls, value: str) -> str:
        validate_news_summary(value)
        return value


class NewsDraft(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    items: list[NewsDraftItem] = Field(min_length=1, max_length=2)
    editorial_note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def distinct_articles(self):
        ids = [id for item in self.items for id in item.evidence_ids]
        if len(ids) != len(set(ids)):
            raise ValueError("Each article belongs in exactly one news item")
        return self
