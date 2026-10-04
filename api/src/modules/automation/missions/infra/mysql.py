from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlmodel import col

from src.modules.automation.missions.domain.dtos import (
    MissionChange,
    MissionClaim,
)
from src.modules.automation.missions.domain.models import (
    MissionEventModel,
    MissionModel,
)
from src.modules.automation.missions.infra.tables import (
    MissionEventTable,
    MissionTable,
)


class MissionRepository(MySQLRepository[MissionModel]):
    table = MissionTable

    async def get(self, id: int, *, lock: bool = False) -> MissionModel | None:
        stmt = select(self.table).where(col(self.table.id) == id)
        if lock:
            stmt = stmt.with_for_update().execution_options(
                populate_existing=True
            )
        result = await self.uow.execute(stmt)
        return result.scalar_one_or_none()

    async def by_update(
        self, bot_id: int, update_id: int
    ) -> MissionModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(
                col(self.table.bot_id) == bot_id,
                col(self.table.update_id) == update_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def active_count(self, owner_id: int) -> int:
        result = await self.uow.execute(
            select(col(self.table.id))
            .where(
                col(self.table.owner_id) == owner_id,
                col(self.table.status).in_(["queued", "running", "waiting"]),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return len(result.all())

    async def page(
        self, owner_id: int, offset: int, limit: int
    ) -> tuple[Sequence[MissionModel], int]:
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

    async def claim(self, id: int, data: MissionClaim) -> bool:
        result = await self.uow.execute(
            update(self.table)
            .execution_options(synchronize_session=False)
            .where(
                col(self.table.id) == id,
                col(self.table.status) == "queued",
                col(self.table.version) == data.version,
                col(self.table.deadline) > data.now,
            )
            .values(
                status="running",
                version=data.version + 1,
                lease_expires_at=data.lease_expires_at,
            )
        )
        return cast(CursorResult[Any], result).rowcount == 1

    async def change(self, id: int, data: MissionChange) -> None:
        await self.uow.execute(
            update(self.table)
            .execution_options(synchronize_session=False)
            .where(col(self.table.id) == id)
            .values(**data.model_dump(), version=col(self.table.version) + 1)
        )

    async def due(self, limit: int) -> Sequence[MissionModel]:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.status) == "queued")
            .order_by(col(self.table.id))
            .limit(limit)
        )
        return result.scalars().all()

    async def expire_running(self, now: datetime) -> None:
        await self.uow.execute(
            update(self.table)
            .execution_options(synchronize_session=False)
            .where(
                col(self.table.status) == "running",
                col(self.table.lease_expires_at) <= now,
            )
            .values(
                status="failed",
                stage="interrupted",
                failure_reason=(
                    "Execution interrupted; no automatic model replay"
                ),
            )
        )


class MissionEventRepository(MySQLRepository[MissionEventModel]):
    table = MissionEventTable
