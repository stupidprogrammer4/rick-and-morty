from collections.abc import Sequence

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from sqlmodel import col

from src.modules.content.drafts.infra.tables import DraftEvidenceTable
from src.modules.content.news.domain.models import ArticleModel
from src.modules.content.news.infra.tables import ArticleTable
from src.modules.content.publications.infra.tables import PublicationTable


class ArticleRepository(MySQLRepository[ArticleModel]):
    table = ArticleTable

    async def published_url_hashes(self) -> set[str]:
        result = await self.uow.execute(
            select(col(ArticleTable.url_hash))
            .join(
                DraftEvidenceTable,
                col(DraftEvidenceTable.article_id) == col(ArticleTable.id),
            )
            .join(
                PublicationTable,
                col(PublicationTable.draft_id)
                == col(DraftEvidenceTable.draft_id),
            )
            .where(
                col(PublicationTable.status).in_(
                    ["queued", "sending", "sent", "unknown"]
                )
            )
            .distinct()
        )
        return set(result.scalars().all())

    async def save_many(self, data: Sequence[ArticleModel]) -> None:
        if not data:
            return
        stmt = insert(self.table).values([row.to_row() for row in data])
        await self.uow.execute(
            stmt.on_duplicate_key_update(
                body=stmt.inserted.body,
                fetched_at=stmt.inserted.fetched_at,
                content_hash=stmt.inserted.content_hash,
            )
        )

    async def for_mission(self, mission_id: int) -> Sequence[ArticleModel]:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.mission_id) == mission_id)
            .order_by(col(self.table.id))
        )
        return result.scalars().all()

    async def get(self, mission_id: int, id: int) -> ArticleModel | None:
        result = await self.uow.execute(
            select(self.table).where(
                col(self.table.id) == id,
                col(self.table.mission_id) == mission_id,
            )
        )
        return result.scalar_one_or_none()
