from collections.abc import Awaitable
from typing import Protocol

from src.modules.news.domain.dtos import (
    ArticleEvidence,
    ArticleInput,
    CollectNews,
)


class INewsCollector(Protocol):
    def collect(self, data: CollectNews) -> Awaitable[list[ArticleInput]]: ...
    def read_url(self, url: str) -> Awaitable[ArticleInput]: ...


class IArticleService(Protocol):
    def collect(
        self, mission_id: int, data: CollectNews
    ) -> Awaitable[list[ArticleEvidence]]: ...
    def read_url(
        self, mission_id: int, url: str
    ) -> Awaitable[ArticleEvidence]: ...
    def read(self, mission_id: int, id: int) -> Awaitable[ArticleEvidence]: ...
    def list(self, mission_id: int) -> Awaitable[list[ArticleEvidence]]: ...
