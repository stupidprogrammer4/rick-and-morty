from collections.abc import Sequence

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import func, select, update
from sqlalchemy.dialects.mysql import insert
from sqlmodel import col

from src.modules.content.domain.models import DraftEvidenceModel, DraftModel
from src.modules.content.infra.tables import DraftEvidenceTable, DraftTable


class DraftRepository(MySQLRepository[DraftModel]):
    table = DraftTable

    async def get(self, id: int, *, lock: bool = False) -> DraftModel | None:
        stmt = select(self.table).where(col(self.table.id) == id)
        if lock:
            stmt = stmt.with_for_update().execution_options(
                populate_existing=True
            )
        result = await self.uow.execute(stmt)
        return result.scalar_one_or_none()

    async def by_key(self, key: str) -> DraftModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.idempotency_key) == key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def page(
        self, owner_id: int, offset: int, limit: int
    ) -> tuple[Sequence[DraftModel], int]:
        condition = col(self.table.owner_id) == owner_id
        result = await self.uow.execute(
            select(self.table)
            .where(condition)
            .order_by(col(self.table.id).desc())
            .offset(offset)
            .limit(limit)
        )
        total = await self.uow.execute(
            select(func.count()).select_from(self.table).where(condition)
        )
        return result.scalars().all(), total.scalar_one()

    async def save(self, model: DraftModel) -> None:
        await self.uow.execute(
            update(self.table)
            .execution_options(synchronize_session=False)
            .where(col(self.table.id) == model.id)
            .values(**model.model_dump(exclude={"id", "created_at"}))
        )


class DraftEvidenceRepository(MySQLRepository[DraftEvidenceModel]):
    table = DraftEvidenceTable

    async def link_many(self, rows: Sequence[DraftEvidenceModel]) -> None:
        if not rows:
            return
        stmt = insert(self.table).values([row.to_row() for row in rows])
        await self.uow.execute(
            stmt.on_duplicate_key_update(article_id=stmt.inserted.article_id)
        )
