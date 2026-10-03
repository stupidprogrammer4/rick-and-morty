from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import select
from sqlmodel import col

from src.modules.market.domain.models import MarketSnapshotModel
from src.modules.market.infra.tables import MarketSnapshotTable


class MarketSnapshotRepository(MySQLRepository[MarketSnapshotModel]):
    table = MarketSnapshotTable

    async def get(self, id: int) -> MarketSnapshotModel | None:
        result = await self.uow.execute(
            select(self.table).where(col(self.table.id) == id)
        )
        return result.scalar_one_or_none()

    async def by_mission(self, mission_id: int) -> MarketSnapshotModel | None:
        result = await self.uow.execute(
            select(self.table).where(col(self.table.mission_id) == mission_id)
        )
        return result.scalar_one_or_none()
