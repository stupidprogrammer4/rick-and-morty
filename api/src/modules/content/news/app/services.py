from papilio.infra.db.transaction import transaction

from src.modules.content.news.domain.dtos import ArticleEvidence, CollectNews
from src.modules.content.news.domain.models import ArticleModel
from src.modules.content.news.infra.mysql import ArticleRepository
from src.modules.content.news.infra.sources import digest
from src.modules.content.news.interfaces import INewsCollector
from src.shared.errors import missing


class ArticleService:
    def __init__(self, repo: ArticleRepository, collector: INewsCollector):
        self.repo = repo
        self.collector = collector

    async def collect(
        self, mission_id: int, data: CollectNews
    ) -> list[ArticleEvidence]:
        entries = await self.collector.collect(data)
        async with transaction():
            await self.repo.save_many(
                [
                    ArticleModel(
                        **entry.model_dump(),
                        mission_id=mission_id,
                        url_hash=digest(entry.url),
                        content_hash=digest(entry.body),
                    )
                    for entry in entries
                ]
            )
        result = await self.list(mission_id)
        return result

    async def read_url(self, mission_id: int, url: str) -> ArticleEvidence:
        entry = await self.collector.read_url(url)
        async with transaction():
            row = await self.repo.create(
                ArticleModel(
                    **entry.model_dump(),
                    mission_id=mission_id,
                    url_hash=digest(entry.url),
                    content_hash=digest(entry.body),
                )
            )
            result = ArticleEvidence.model_validate(row, from_attributes=True)
        return result

    async def read(self, mission_id: int, id: int) -> ArticleEvidence:
        row = await self.repo.get(mission_id, id)
        if row is None:
            raise missing("article", id)
        return ArticleEvidence.model_validate(row, from_attributes=True)

    async def list(self, mission_id: int) -> list[ArticleEvidence]:
        rows = await self.repo.for_mission(mission_id)
        return [
            ArticleEvidence.model_validate(row, from_attributes=True)
            for row in rows
        ]
