from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert
from sqlmodel import col

from src.modules.ops.guards.domain.models import PortalGuardModel
from src.modules.ops.guards.infra.tables import PortalGuardTable


class PortalGuardRepository(MySQLRepository[PortalGuardModel]):
    table = PortalGuardTable

    async def lock(self, key: str) -> PortalGuardModel:
        stmt = insert(self.table).values(key=key, paused=False)
        await self.uow.execute(
            stmt.on_duplicate_key_update(key=stmt.inserted.key)
        )
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.key) == key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one()

    async def get(self, key: str) -> PortalGuardModel | None:
        result = await self.uow.execute(
            select(self.table).where(col(self.table.key) == key)
        )
        return result.scalar_one_or_none()

    async def set_paused(self, key: str, paused: bool) -> None:
        await self.uow.execute(
            update(self.table)
            .execution_options(synchronize_session=False)
            .where(col(self.table.key) == key)
            .values(paused=paused)
        )
