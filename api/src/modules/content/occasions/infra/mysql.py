from collections.abc import Sequence
from typing import cast

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import func, select, update
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.engine import CursorResult
from sqlmodel import col

from src.modules.content.occasions.domain.dtos import OccasionChange
from src.modules.content.occasions.domain.models import OccasionModel
from src.modules.content.occasions.infra.tables import OccasionTable


class OccasionRepository(MySQLRepository[OccasionModel]):
    table = OccasionTable

    async def by_key(self, key: str) -> OccasionModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.key) == key)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def active(self) -> Sequence[OccasionModel]:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.enabled).is_(True))
            .order_by(col(self.table.id))
        )
        return result.scalars().all()

    async def page(
        self, query: str, page: int, per_page: int
    ) -> Sequence[OccasionModel]:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.definition).contains(query, autoescape=True))
            .order_by(col(self.table.id))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return result.scalars().all()

    async def count(self, query: str) -> int:
        result = await self.uow.execute(
            select(func.count())
            .select_from(self.table)
            .where(col(self.table.definition).contains(query, autoescape=True))
        )
        return result.scalar_one()

    async def change(
        self, id: int, data: OccasionChange, revision: int
    ) -> bool:
        result = await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.id) == id, col(self.table.revision) == revision
            )
            .values(**data.model_dump())
            .execution_options(synchronize_session=False)
        )
        return cast(CursorResult, result).rowcount == 1

    async def seed_many(self, rows: Sequence[OccasionModel]) -> None:
        if not rows:
            return
        stmt = insert(self.table).values([row.to_row() for row in rows])
        await self.uow.execute(
            stmt.on_duplicate_key_update(key=stmt.inserted.key)
        )
