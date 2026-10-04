import asyncio
import json
from datetime import UTC, datetime
from urllib.parse import urlencode

from pydantic import BaseModel, Field

from src.modules.content.news.domain.dtos import (
    ArticleInput,
    CollectNews,
    NewsSource,
)
from src.shared.dates import utc_now
from src.shared.http import SourceHTTPClient


class HNSearchHit(BaseModel):
    objectID: str
    title: str | None = None
    url: str | None = None
    created_at_i: int


class HNSearchResponse(BaseModel):
    hits: list[HNSearchHit] = Field(default_factory=list)


class HackerNewsSource:
    def __init__(self, http: SourceHTTPClient, source: NewsSource):
        self.http = http
        self.source = source

    async def search(self, data: CollectNews) -> list[ArticleInput]:
        words = set(data.topic.lower().split())
        subjects = sorted(self.source.topics.intersection(words))
        if not subjects:
            subjects = self.source.default_topics
        pages = await asyncio.gather(
            *(
                self.query(subject, int(data.since.timestamp()))
                for subject in subjects[:3]
            )
        )
        hits = {hit.objectID: hit for page in pages for hit in page.hits}
        result: list[ArticleInput] = []
        for hit in hits.values():
            if (
                not hit.url
                or not hit.title
                or not hit.url.startswith("https://")
            ):
                continue
            timestamp = datetime.fromtimestamp(hit.created_at_i, UTC)
            if timestamp < data.since or timestamp > utc_now():
                continue
            result.append(
                ArticleInput(
                    source_id=self.source.id,
                    url=hit.url,
                    title=hit.title[:300],
                    published_at=timestamp,
                    fetched_at=utc_now(),
                    body="",
                )
            )
        return result

    async def query(self, subject: str, since: int) -> HNSearchResponse:
        query = urlencode(
            {
                "query": subject,
                "tags": "story",
                "numericFilters": f"created_at_i>{since}",
                "hitsPerPage": self.source.search_page_size,
            }
        )
        raw = await self.http.get(
            str(self.source.feed_url) + "?" + query,
            self.source.allowed_hosts,
            maximum_bytes=300000,
        )
        return HNSearchResponse.model_validate(json.loads(raw))
